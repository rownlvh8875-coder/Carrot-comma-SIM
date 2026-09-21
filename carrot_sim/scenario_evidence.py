from __future__ import annotations

"""Typed scenario/evidence contract for real, synthetic, diagnostic, and holdout data.

This module is deliberately independent from the older lightweight Scenario class.
It governs *scientific role and provenance*, not the numerical scenario dynamics.
"""

from dataclasses import dataclass, field
import re

FULL_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FULL_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

SOURCE_KINDS = {"real_recorded", "synthetic_derived", "synthetic_world"}
SCIENTIFIC_ROLES = {
  "longitudinal_tuning",
  "radar_negative_regression",
  "lateral_assurance",
  "integration_stress",
}
EVIDENCE_ROLES = {"development", "diagnostic", "sealed_holdout", "synthetic_stress"}
SYNTHETIC_EVIDENCE_ROLES = {"diagnostic", "synthetic_stress"}


@dataclass(frozen=True)
class ScenarioEvidence:
  scenario_id: str
  source_kind: str
  scientific_role: str
  evidence_role: str
  target_vehicle: str = "SYNTHETIC_GENERIC"
  raw_sha256: str | None = None
  parent_scenario_ids: tuple[str, ...] = ()
  generator_id: str | None = None
  settings_signature_sha256: str | None = None
  historical_git_commit: str | None = None
  historical_dirty: bool | None = None
  atomic_boot_provenance: bool = False
  metadata: dict[str, object] = field(default_factory=dict)

  def __post_init__(self) -> None:
    if not self.scenario_id.strip():
      raise ValueError("scenario_id is required")
    if self.source_kind not in SOURCE_KINDS:
      raise ValueError(f"unsupported source_kind: {self.source_kind}")
    if self.scientific_role not in SCIENTIFIC_ROLES:
      raise ValueError(f"unsupported scientific_role: {self.scientific_role}")
    if self.evidence_role not in EVIDENCE_ROLES:
      raise ValueError(f"unsupported evidence_role: {self.evidence_role}")
    if self.target_vehicle != "SYNTHETIC_GENERIC":
      raise ValueError("public scenario evidence target must be SYNTHETIC_GENERIC")

    if self.raw_sha256 is not None and not FULL_SHA256_RE.fullmatch(self.raw_sha256):
      raise ValueError("raw_sha256 must be a full lowercase SHA256")
    if self.settings_signature_sha256 is not None and not FULL_SHA256_RE.fullmatch(self.settings_signature_sha256):
      raise ValueError("settings_signature_sha256 must be a full lowercase SHA256")
    if self.historical_git_commit is not None and not FULL_GIT_SHA_RE.fullmatch(self.historical_git_commit):
      raise ValueError("historical_git_commit must be a full lowercase Git SHA")

    if self.source_kind == "real_recorded":
      if self.raw_sha256 is None:
        raise ValueError("real_recorded evidence requires raw_sha256")
      if self.evidence_role == "synthetic_stress":
        raise ValueError("real_recorded evidence may not use synthetic_stress role")
    else:
      if not self.parent_scenario_ids and not (self.generator_id or "").strip():
        raise ValueError("synthetic evidence requires parent_scenario_ids or generator_id")
      if self.evidence_role not in SYNTHETIC_EVIDENCE_ROLES:
        raise ValueError("synthetic evidence may only be diagnostic or synthetic_stress")

    if self.scientific_role == "radar_negative_regression" and self.evidence_role == "sealed_holdout":
      raise ValueError("radar_negative_regression may not be promoted to sealed_holdout")

  @property
  def is_synthetic(self) -> bool:
    return self.source_kind != "real_recorded"

  @property
  def historical_H1_eligible(self) -> bool:
    return bool(
      self.source_kind == "real_recorded"
      and self.scientific_role == "longitudinal_tuning"
      and self.evidence_role in {"development", "diagnostic", "sealed_holdout"}
      and self.historical_dirty is False
      and self.raw_sha256
      and self.settings_signature_sha256
      and self.historical_git_commit
      and self.atomic_boot_provenance
    )

  @property
  def real_route_acceptance_eligible(self) -> bool:
    return bool(
      self.source_kind == "real_recorded"
      and self.historical_dirty is False
      and self.evidence_role in {"development", "sealed_holdout"}
    )

  def assert_holdout_sealed(self, *, opening_authorized: bool = False) -> None:
    if self.evidence_role == "sealed_holdout" and not opening_authorized:
      raise RuntimeError("sealed holdout may not be opened by default")


def validate_role_separation(records: list[ScenarioEvidence]) -> list[str]:
  """Return cross-record role/provenance violations without mutating evidence."""

  violations: list[str] = []
  seen_ids: set[str] = set()
  for record in records:
    if record.scenario_id in seen_ids:
      violations.append(f"duplicate_scenario_id:{record.scenario_id}")
    seen_ids.add(record.scenario_id)

    if record.is_synthetic and record.real_route_acceptance_eligible:
      violations.append(f"synthetic_marked_acceptance_eligible:{record.scenario_id}")
    if record.scientific_role == "radar_negative_regression" and record.historical_H1_eligible:
      violations.append(f"radar_negative_marked_H1_eligible:{record.scenario_id}")

  return violations
