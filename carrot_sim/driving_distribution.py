from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping

from .campaign_manifest import content_sha256


@dataclass(frozen=True)
class FeatureRow:
  route_id: str
  features: Mapping[str, float]
  strata: Mapping[str, str]
  units: Mapping[str, str]


@dataclass(frozen=True)
class DistributionConfig:
  min_stratum_count: int
  quantiles: tuple[float, ...]
  fallback_order: tuple[tuple[str, ...], ...]
  partition_hash: str

  def __post_init__(self) -> None:
    if self.min_stratum_count <= 0:
      raise ValueError("min_stratum_count must be positive")
    if not self.quantiles or any(not 0.0 <= q <= 1.0 for q in self.quantiles):
      raise ValueError("quantiles must be in [0,1]")
    if not self.fallback_order or self.fallback_order[-1] != ():
      raise ValueError("fallback_order must end with the global stratum")


@dataclass(frozen=True)
class FeatureStats:
  count: int
  minimum: float
  maximum: float
  mean: float
  quantiles: dict[str, float]
  unit: str

  def to_artifact(self) -> dict[str, object]:
    return {
      "count": self.count,
      "minimum": self.minimum,
      "maximum": self.maximum,
      "mean": self.mean,
      "quantiles": self.quantiles,
      "unit": self.unit,
    }


@dataclass(frozen=True)
class StratumDistribution:
  source_count: int
  effective_count: int
  fallback_level: str
  features: dict[str, FeatureStats]

  def to_artifact(self) -> dict[str, object]:
    return {
      "source_count": self.source_count,
      "effective_count": self.effective_count,
      "fallback_level": self.fallback_level,
      "features": {name: stats.to_artifact() for name, stats in sorted(self.features.items())},
    }


@dataclass(frozen=True)
class DistributionModel:
  schema_version: int
  partition_hash: str
  route_count: int
  row_count: int
  strata: dict[str, StratumDistribution]
  transitions: dict[str, dict[str, int]]
  model_hash: str

  def to_artifact(self) -> dict[str, object]:
    return {
      "schema_version": self.schema_version,
      "partition_hash": self.partition_hash,
      "route_count": self.route_count,
      "row_count": self.row_count,
      "strata": {name: value.to_artifact() for name, value in sorted(self.strata.items())},
      "transitions": {
        source: dict(sorted(targets.items()))
        for source, targets in sorted(self.transitions.items())
      },
      "model_hash": self.model_hash,
    }


def _stratum_key(row: FeatureRow, fields: tuple[str, ...]) -> str:
  if not fields:
    return "global"
  return "|".join(f"{name}={row.strata.get(name, 'unknown')}" for name in fields)


def _quantile(values: list[float], q: float) -> float:
  ordered = sorted(values)
  if len(ordered) == 1:
    return ordered[0]
  position = q * (len(ordered) - 1)
  lower = int(math.floor(position))
  upper = int(math.ceil(position))
  if lower == upper:
    return ordered[lower]
  fraction = position - lower
  return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _stats(rows: list[FeatureRow], quantiles: tuple[float, ...], units: dict[str, str]) -> dict[str, FeatureStats]:
  names = sorted({name for row in rows for name in row.features})
  result: dict[str, FeatureStats] = {}
  for name in names:
    values = [float(row.features[name]) for row in rows if name in row.features]
    result[name] = FeatureStats(
      count=len(values),
      minimum=min(values),
      maximum=max(values),
      mean=sum(values) / len(values),
      quantiles={format(q, "g"): _quantile(values, q) for q in quantiles},
      unit=units[name],
    )
  return result


def learn_distribution(rows: Iterable[FeatureRow], config: DistributionConfig) -> DistributionModel:
  source_rows = list(rows)
  if not source_rows:
    raise ValueError("at least one training row is required")
  units: dict[str, str] = {}
  for row in source_rows:
    if row.strata.get("split") != "train":
      raise ValueError("distribution learner accepts the training partition only")
    if not row.route_id.strip():
      raise ValueError("route_id is required")
    for name, raw in row.features.items():
      value = float(raw)
      if not math.isfinite(value):
        raise ValueError(f"feature {name} must be finite")
      unit = row.units.get(name)
      if not unit:
        raise ValueError(f"feature {name} requires a unit")
      previous = units.setdefault(name, unit)
      if previous != unit:
        raise ValueError(f"unit conflict for {name}: {previous} != {unit}")

  leaf_fields = config.fallback_order[0]
  leaf_groups: dict[str, list[FeatureRow]] = {}
  for row in source_rows:
    leaf_groups.setdefault(_stratum_key(row, leaf_fields), []).append(row)

  strata: dict[str, StratumDistribution] = {}
  for leaf_key, leaf_rows in sorted(leaf_groups.items()):
    effective = leaf_rows
    level = "|".join(leaf_fields) or "global"
    if len(leaf_rows) < config.min_stratum_count:
      exemplar = leaf_rows[0]
      for fields in config.fallback_order[1:]:
        candidate = [row for row in source_rows if _stratum_key(row, fields) == _stratum_key(exemplar, fields)]
        if len(candidate) >= config.min_stratum_count or fields == ():
          effective = candidate
          level = "|".join(fields) or "global"
          break
    strata[leaf_key] = StratumDistribution(
      source_count=len(leaf_rows),
      effective_count=len(effective),
      fallback_level=level,
      features=_stats(effective, config.quantiles, units),
    )

  by_route: dict[str, list[str]] = {}
  for row in source_rows:
    by_route.setdefault(row.route_id, []).append(_stratum_key(row, leaf_fields))
  transitions: dict[str, dict[str, int]] = {}
  for keys in by_route.values():
    for source, target in zip(keys, keys[1:]):
      targets = transitions.setdefault(source, {})
      targets[target] = targets.get(target, 0) + 1

  payload = {
    "schema_version": 1,
    "partition_hash": config.partition_hash,
    "route_count": len(by_route),
    "row_count": len(source_rows),
    "strata": {name: value.to_artifact() for name, value in sorted(strata.items())},
    "transitions": {name: dict(sorted(value.items())) for name, value in sorted(transitions.items())},
  }
  return DistributionModel(1, config.partition_hash, len(by_route), len(source_rows), strata, transitions, content_sha256(payload))


def distribution_model_from_artifact(artifact: Mapping[str, object]) -> DistributionModel:
  raw_strata = artifact.get("strata")
  if not isinstance(raw_strata, dict):
    raise ValueError("distribution artifact requires strata")
  strata: dict[str, StratumDistribution] = {}
  for name, raw in raw_strata.items():
    if not isinstance(raw, dict) or not isinstance(raw.get("features"), dict):
      raise ValueError(f"invalid stratum artifact: {name}")
    features = {
      feature_name: FeatureStats(
        count=int(stats["count"]),
        minimum=float(stats["minimum"]),
        maximum=float(stats["maximum"]),
        mean=float(stats["mean"]),
        quantiles={str(q): float(value) for q, value in stats["quantiles"].items()},
        unit=str(stats["unit"]),
      )
      for feature_name, stats in raw["features"].items()
    }
    strata[str(name)] = StratumDistribution(
      source_count=int(raw["source_count"]),
      effective_count=int(raw["effective_count"]),
      fallback_level=str(raw["fallback_level"]),
      features=features,
    )
  transitions = {
    str(source): {str(target): int(count) for target, count in targets.items()}
    for source, targets in dict(artifact.get("transitions", {})).items()
  }
  model = DistributionModel(
    schema_version=int(artifact["schema_version"]),
    partition_hash=str(artifact["partition_hash"]),
    route_count=int(artifact["route_count"]),
    row_count=int(artifact["row_count"]),
    strata=strata,
    transitions=transitions,
    model_hash=str(artifact["model_hash"]),
  )
  payload = model.to_artifact()
  payload.pop("model_hash")
  if content_sha256(payload) != model.model_hash:
    raise ValueError("distribution artifact hash mismatch")
  return model
