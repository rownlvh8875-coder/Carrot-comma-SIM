from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Mapping

from .campaign_manifest import content_sha256


@dataclass(frozen=True)
class ParameterAxis:
  name: str
  minimum: int
  maximum: int
  step: int
  phase: str

  def __post_init__(self) -> None:
    if not self.name.strip() or self.phase not in {"oat", "interaction", "pareto", "confirmation"}:
      raise ValueError("axis name and phase are required")
    if self.step <= 0 or self.minimum > self.maximum:
      raise ValueError("axis requires positive step and ordered bounds")
    if (self.maximum - self.minimum) % self.step:
      raise ValueError("axis step must divide the inclusive range")

  def values(self) -> tuple[int, ...]:
    return tuple(range(self.minimum, self.maximum + 1, self.step))

  def validate(self, value: int) -> None:
    if not isinstance(value, int) or value < self.minimum or value > self.maximum:
      raise ValueError(f"{self.name} is outside declared bounds")
    if (value - self.minimum) % self.step:
      raise ValueError(f"{self.name} is not on the declared integer grid")


@dataclass(frozen=True)
class ParameterCandidate:
  changes: dict[str, int]
  candidate_id: str
  phase: str


@dataclass(frozen=True)
class SearchSpace:
  axes: tuple[ParameterAxis, ...]

  def __post_init__(self) -> None:
    names = [axis.name for axis in self.axes]
    if not self.axes or len(names) != len(set(names)):
      raise ValueError("search axes must be non-empty and unique")

  def candidate(self, changes: Mapping[str, int], phase: str = "oat") -> ParameterCandidate:
    axes = {axis.name: axis for axis in self.axes}
    if not changes or any(name not in axes for name in changes):
      raise ValueError("candidate contains unknown or empty changes")
    normalized = {name: int(value) for name, value in sorted(changes.items())}
    for name, value in normalized.items():
      axes[name].validate(value)
    digest = content_sha256({"phase": phase, "changes": normalized})
    return ParameterCandidate(normalized, digest, phase)

  def oat_candidates(self, baseline: Mapping[str, int], *, active_axes: set[str]) -> tuple[ParameterCandidate, ...]:
    result = []
    for axis in sorted(self.axes, key=lambda item: item.name):
      if axis.name not in active_axes:
        continue
      for value in axis.values():
        if value != baseline.get(axis.name):
          result.append(self.candidate({axis.name: value}, "oat"))
    return tuple(result)

  def interaction_candidates(self, baseline: Mapping[str, int], *, active_axes: set[str]) -> tuple[ParameterCandidate, ...]:
    eligible = sorted((axis for axis in self.axes if axis.name in active_axes), key=lambda item: item.name)
    result: list[ParameterCandidate] = []
    for left, right in combinations(eligible, 2):
      left_values = tuple(value for value in left.values() if value != baseline.get(left.name))
      right_values = tuple(value for value in right.values() if value != baseline.get(right.name))
      for left_value, right_value in product(left_values, right_values):
        result.append(self.candidate({left.name: left_value, right.name: right_value}, "interaction"))
    return tuple(result)
