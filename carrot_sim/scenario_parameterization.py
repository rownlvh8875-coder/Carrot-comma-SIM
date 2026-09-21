from __future__ import annotations

"""Lightweight logical-scenario parameterization for laptop-scale testing.

The design follows the same high-level idea as Scenic / OpenSCENARIO DSL:
define a logical scenario once, then instantiate many concrete cases from
explicit parameter ranges.  This module intentionally avoids an external DSL
runtime and produces synthetic-stress evidence only.
"""

from dataclasses import dataclass
import hashlib
import math
from typing import Mapping

from .scenario_evidence import ScenarioEvidence


@dataclass(frozen=True)
class ParameterRange:
  name: str
  minimum: float
  maximum: float

  def __post_init__(self) -> None:
    if not self.name.strip():
      raise ValueError("parameter name is required")
    lo = float(self.minimum)
    hi = float(self.maximum)
    if not math.isfinite(lo) or not math.isfinite(hi):
      raise ValueError("parameter bounds must be finite")
    if lo > hi:
      raise ValueError("parameter minimum must be <= maximum")

  def denormalize(self, unit_value: float) -> float:
    u = float(unit_value)
    if not math.isfinite(u) or not 0.0 <= u <= 1.0:
      raise ValueError("unit_value must be finite in [0,1]")
    return self.minimum + (self.maximum - self.minimum) * u


@dataclass(frozen=True)
class ScenarioSample:
  template_id: str
  sample_index: int
  parameters: Mapping[str, float]
  sample_sha256: str
  evidence: ScenarioEvidence


@dataclass(frozen=True)
class LogicalScenarioTemplate:
  template_id: str
  parameters: tuple[ParameterRange, ...]
  scientific_role: str = "integration_stress"
  generator_id: str = "carrot-logical-scenario-v1"
  parent_scenario_ids: tuple[str, ...] = ()

  def __post_init__(self) -> None:
    if not self.template_id.strip():
      raise ValueError("template_id is required")
    if not self.parameters:
      raise ValueError("at least one parameter is required")
    names = [x.name for x in self.parameters]
    if len(names) != len(set(names)):
      raise ValueError("scenario parameter names must be unique")
    if self.scientific_role not in {"integration_stress", "lateral_assurance"}:
      raise ValueError("logical scenario template is restricted to synthetic stress roles")
    if not self.generator_id.strip():
      raise ValueError("generator_id is required")

  def sample(self, sample_index: int) -> ScenarioSample:
    if sample_index < 0:
      raise ValueError("sample_index must be >= 0")
    bases = _first_primes(len(self.parameters))
    params = {
      param.name: param.denormalize(_radical_inverse(sample_index + 1, base))
      for param, base in zip(self.parameters, bases, strict=True)
    }
    canonical = "\n".join(
      [self.template_id, str(sample_index)]
      + [f"{name}={params[name]:.17g}" for name in sorted(params)]
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    scenario_id = f"synthetic_{self.template_id}_{sample_index:06d}_{digest[:12]}"
    evidence = ScenarioEvidence(
      scenario_id=scenario_id,
      source_kind="synthetic_world",
      scientific_role=self.scientific_role,
      evidence_role="synthetic_stress",
      parent_scenario_ids=self.parent_scenario_ids,
      generator_id=self.generator_id,
      metadata={
        "logical_template_id": self.template_id,
        "sample_index": sample_index,
        "sampling": "deterministic_halton",
        "sample_sha256": digest,
        "real_route_acceptance_eligible": False,
        "parameter_tuning_authorized": False,
      },
    )
    return ScenarioSample(
      template_id=self.template_id,
      sample_index=sample_index,
      parameters=params,
      sample_sha256=digest,
      evidence=evidence,
    )


def _radical_inverse(index: int, base: int) -> float:
  if index <= 0 or base < 2:
    raise ValueError("radical inverse requires index > 0 and base >= 2")
  inverse = 1.0 / base
  factor = inverse
  result = 0.0
  n = index
  while n:
    result += factor * (n % base)
    n //= base
    factor *= inverse
  return result


def _first_primes(count: int) -> list[int]:
  if count <= 0:
    return []
  primes: list[int] = []
  candidate = 2
  while len(primes) < count:
    is_prime = True
    root = int(math.sqrt(candidate))
    for p in primes:
      if p > root:
        break
      if candidate % p == 0:
        is_prime = False
        break
    if is_prime:
      primes.append(candidate)
    candidate += 1
  return primes
