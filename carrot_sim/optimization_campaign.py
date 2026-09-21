from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from .campaign_manifest import canonical_json


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PHASES = ("partition", "learn", "generate", "simulate", "safety", "search", "holdout", "report", "complete")


@dataclass(frozen=True)
class CampaignStatus:
  manifest_hash: str
  settings_sha256: str
  phase: str
  completed_phases: tuple[str, ...]
  artifacts: dict[str, object]
  max_workers: int
  blocked_reason: str | None
  real_vehicle_write: bool = False
  deployment_authorized: bool = False

  def to_artifact(self) -> dict[str, object]:
    return {
      "schema_version": 1,
      "manifest_hash": self.manifest_hash,
      "settings_sha256": self.settings_sha256,
      "phase": self.phase,
      "completed_phases": self.completed_phases,
      "artifacts": self.artifacts,
      "max_workers": self.max_workers,
      "blocked_reason": self.blocked_reason,
      "real_vehicle_write": False,
      "deployment_authorized": False,
    }


class OptimizationCampaign:
  def __init__(self, root: Path, status: CampaignStatus) -> None:
    self.root = root
    self._status = status

  @classmethod
  def create(
    cls,
    root: str | Path,
    manifest_hash: str,
    settings_path: str | Path,
    *,
    max_workers: int,
    min_free_bytes: int = 100_000_000,
  ) -> "OptimizationCampaign":
    if not _SHA256.fullmatch(manifest_hash):
      raise ValueError("manifest_hash must be lowercase SHA-256")
    if not 1 <= max_workers <= 8:
      raise ValueError("max_workers must be between 1 and 8")
    destination = Path(root)
    destination.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination).free < min_free_bytes:
      raise RuntimeError("insufficient disk space")
    settings_bytes = Path(settings_path).read_bytes()
    json.loads(settings_bytes)
    status = CampaignStatus(manifest_hash, hashlib.sha256(settings_bytes).hexdigest(),
                            "initialized", (), {}, max_workers, None)
    campaign = cls(destination, status)
    campaign._write()
    return campaign

  @classmethod
  def resume(cls, root: str | Path, manifest_hash: str) -> "OptimizationCampaign":
    destination = Path(root)
    artifact = json.loads((destination / "status.json").read_text(encoding="utf-8"))
    if artifact["manifest_hash"] != manifest_hash:
      raise RuntimeError("campaign manifest mismatch")
    status = CampaignStatus(
      artifact["manifest_hash"], artifact["settings_sha256"], artifact["phase"],
      tuple(artifact["completed_phases"]), dict(artifact["artifacts"]),
      int(artifact["max_workers"]), artifact.get("blocked_reason"),
    )
    return cls(destination, status)

  def _write(self) -> None:
    payload = canonical_json(self._status.to_artifact()) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.root, delete=False) as handle:
      temporary = Path(handle.name)
      handle.write(payload)
      handle.flush()
    temporary.replace(self.root / "status.json")

  def status(self) -> CampaignStatus:
    return self._status

  def advance(self, phase: str, artifacts: dict[str, object] | None = None) -> None:
    if self._status.phase == "blocked":
      raise RuntimeError("blocked campaign cannot advance")
    completed = self._status.completed_phases
    expected = _PHASES[len(completed)]
    if phase != expected:
      raise ValueError(f"phase order violation: expected {expected}, got {phase}")
    merged = dict(self._status.artifacts)
    if artifacts is not None:
      merged[phase] = artifacts
    self._status = CampaignStatus(
      self._status.manifest_hash, self._status.settings_sha256, phase,
      completed + (phase,), merged, self._status.max_workers, None,
    )
    self._write()

  def block(self, reason: str) -> None:
    if not reason:
      raise ValueError("blocked reason is required")
    self._status = CampaignStatus(
      self._status.manifest_hash, self._status.settings_sha256, "blocked",
      self._status.completed_phases, self._status.artifacts,
      self._status.max_workers, reason,
    )
    self._write()
