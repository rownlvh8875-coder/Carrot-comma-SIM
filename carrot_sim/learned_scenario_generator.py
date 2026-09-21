from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random
from typing import Iterable

from .campaign_manifest import content_sha256
from .driving_distribution import DistributionModel


@dataclass(frozen=True)
class ScenarioGeneratorConfig:
  families: tuple[str, ...]
  boundary_stress_every: int = 0
  tail_expansion_fraction: float = 0.05
  max_per_stratum: int = 100

  def __post_init__(self) -> None:
    if not self.families or any(not family.strip() for family in self.families):
      raise ValueError("at least one scenario family is required")
    if len(set(self.families)) != len(self.families):
      raise ValueError("scenario families must be unique")
    if self.boundary_stress_every < 0:
      raise ValueError("boundary_stress_every must be >= 0")
    if not 0.0 <= self.tail_expansion_fraction <= 0.25:
      raise ValueError("tail_expansion_fraction must be in [0,0.25]")
    if self.max_per_stratum <= 0:
      raise ValueError("max_per_stratum must be positive")


@dataclass(frozen=True)
class GeneratedScenario:
  scenario_id: str
  family: str
  seed: str
  sample_index: int
  stratum: str
  parameters: dict[str, float]
  sampled_values: dict[str, dict[str, object]]
  plausibility_score: float
  dependency_consistency_score: float
  out_of_distribution: bool
  evidence_role: str
  source_route_count: int
  distribution_hash: str
  content_hash: str
  parameter_tuning_authorized: bool = False
  real_route_acceptance_eligible: bool = False

  def to_artifact(self) -> dict[str, object]:
    return {
      "schema_version": 1,
      "scenario_id": self.scenario_id,
      "family": self.family,
      "seed": self.seed,
      "sample_index": self.sample_index,
      "stratum": self.stratum,
      "parameters": self.parameters,
      "sampled_values": self.sampled_values,
      "plausibility_score": self.plausibility_score,
      "dependency_consistency_score": self.dependency_consistency_score,
      "out_of_distribution": self.out_of_distribution,
      "evidence_role": self.evidence_role,
      "source_route_count": self.source_route_count,
      "distribution_hash": self.distribution_hash,
      "content_hash": self.content_hash,
      "parameter_tuning_authorized": self.parameter_tuning_authorized,
      "real_route_acceptance_eligible": self.real_route_acceptance_eligible,
    }


def _rng(model_hash: str, seed: str, index: int) -> random.Random:
  digest = hashlib.sha256(f"{model_hash}|{seed}|{index}".encode("utf-8")).digest()
  return random.Random(int.from_bytes(digest[:16], "big"))


def generate_scenario(
  model: DistributionModel,
  config: ScenarioGeneratorConfig,
  seed: str,
  sample_index: int,
) -> GeneratedScenario:
  if sample_index < 0:
    raise ValueError("sample_index must be >= 0")
  if not seed:
    raise ValueError("seed is required")
  strata = sorted(model.strata)
  if not strata:
    raise ValueError("distribution model has no strata")
  stratum_name = strata[sample_index % len(strata)]
  stratum = model.strata[stratum_name]
  family = config.families[sample_index % len(config.families)]
  rng = _rng(model.model_hash, seed, sample_index)
  stress = config.boundary_stress_every > 0 and (sample_index + 1) % config.boundary_stress_every == 0
  parameters: dict[str, float] = {}
  sampled: dict[str, dict[str, object]] = {}
  for position, (name, stats) in enumerate(sorted(stratum.features.items())):
    quantile = rng.random()
    value = stats.minimum + (stats.maximum - stats.minimum) * quantile
    is_ood = stress and position == 0
    if is_ood:
      width = max(stats.maximum - stats.minimum, abs(stats.maximum), 1.0)
      value = stats.maximum + width * config.tail_expansion_fraction
    parameters[name] = value
    sampled[name] = {
      "unit": stats.unit,
      "support": [stats.minimum, stats.maximum],
      "quantile": quantile,
      "fallback_level": stratum.fallback_level,
      "out_of_distribution": is_ood,
    }
  payload = {
    "distribution_hash": model.model_hash,
    "family": family,
    "seed": seed,
    "sample_index": sample_index,
    "stratum": stratum_name,
    "parameters": parameters,
    "evidence_role": "synthetic_stress" if stress else "synthetic_search",
  }
  digest = content_sha256(payload)
  return GeneratedScenario(
    scenario_id=f"{family}--{sample_index:06d}--{digest[:12]}",
    family=family,
    seed=seed,
    sample_index=sample_index,
    stratum=stratum_name,
    parameters=parameters,
    sampled_values=sampled,
    plausibility_score=0.5 if stress else 1.0,
    dependency_consistency_score=1.0,
    out_of_distribution=stress,
    evidence_role="synthetic_stress" if stress else "synthetic_search",
    source_route_count=model.route_count,
    distribution_hash=model.model_hash,
    content_hash=digest,
  )


def generate_scenario_pack(
  model: DistributionModel,
  config: ScenarioGeneratorConfig,
  seed: str,
  count: int,
) -> tuple[GeneratedScenario, ...]:
  if count <= 0:
    raise ValueError("count must be positive")
  result: list[GeneratedScenario] = []
  seen: set[str] = set()
  stratum_counts: dict[str, int] = {}
  for index in range(count):
    scenario = generate_scenario(model, config, seed, index)
    if stratum_counts.get(scenario.stratum, 0) >= config.max_per_stratum:
      continue
    if scenario.content_hash in seen:
      continue
    seen.add(scenario.content_hash)
    stratum_counts[scenario.stratum] = stratum_counts.get(scenario.stratum, 0) + 1
    result.append(scenario)
  return tuple(result)
