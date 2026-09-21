from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable

from .campaign_manifest import content_sha256


@dataclass(frozen=True)
class SplitRatios:
  train: int
  search_validation: int
  holdout: int

  def __post_init__(self) -> None:
    values = (self.train, self.search_validation, self.holdout)
    if any(not isinstance(value, int) or value < 0 for value in values):
      raise ValueError("split ratios must be non-negative integers")
    if sum(values) != 100:
      raise ValueError("split ratios must total 100")


@dataclass(frozen=True)
class RoutePartition:
  seed: str
  ratios: SplitRatios
  assignments: dict[str, str]
  manifest_hash: str

  def assert_disjoint(self) -> None:
    route_sets = {
      split: {route for route, assigned in self.assignments.items() if assigned == split}
      for split in ("train", "search_validation", "holdout")
    }
    names = tuple(route_sets)
    for index, left in enumerate(names):
      for right in names[index + 1:]:
        overlap = route_sets[left] & route_sets[right]
        if overlap:
          raise ValueError(f"route leakage between {left} and {right}: {sorted(overlap)}")

  def to_artifact(self) -> dict[str, object]:
    return {
      "schema_version": 1,
      "seed": self.seed,
      "ratios": {
        "train": self.ratios.train,
        "search_validation": self.ratios.search_validation,
        "holdout": self.ratios.holdout,
      },
      "assignments": dict(sorted(self.assignments.items())),
      "manifest_hash": self.manifest_hash,
    }


def _bucket(seed: str, route_id: str) -> int:
  digest = hashlib.sha256(f"{seed}|{route_id}".encode("utf-8")).hexdigest()
  return int(digest[:16], 16) % 100


def build_route_partition(
  route_ids: Iterable[str],
  seed: str,
  ratios: SplitRatios,
) -> RoutePartition:
  if not seed.strip():
    raise ValueError("partition seed is required")
  normalized = sorted(set(route_ids))
  if any(not isinstance(route, str) or not route.strip() for route in normalized):
    raise ValueError("route ids must be non-empty strings")
  train_limit = ratios.train
  validation_limit = train_limit + ratios.search_validation
  assignments: dict[str, str] = {}
  for route_id in normalized:
    bucket = _bucket(seed, route_id)
    assignments[route_id] = (
      "train" if bucket < train_limit
      else "search_validation" if bucket < validation_limit
      else "holdout"
    )
  payload = {
    "schema_version": 1,
    "seed": seed,
    "ratios": ratios.__dict__,
    "assignments": assignments,
  }
  result = RoutePartition(seed, ratios, assignments, content_sha256(payload))
  result.assert_disjoint()
  return result
