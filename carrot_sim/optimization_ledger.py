from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
from typing import Any

from .campaign_manifest import canonical_json


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class LedgerIdentity:
  campaign_hash: str
  split_hash: str
  distribution_hash: str
  scenario_hash: str
  controller_hash: str
  plant_hash: str
  search_config_hash: str
  safety_policy_hash: str

  def __post_init__(self) -> None:
    for name, value in asdict(self).items():
      if not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be lowercase SHA-256")


class OptimizationLedger:
  def __init__(self, path: Path, identity: LedgerIdentity, completed: dict[str, dict[str, Any]]) -> None:
    self.path = path
    self.identity = identity
    self._completed = completed
    self._reserved: set[str] = set()

  @classmethod
  def open(cls, path: str | Path, identity: LedgerIdentity) -> "OptimizationLedger":
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
      destination.write_text(canonical_json({"kind": "header", "identity": asdict(identity)}) + "\n", encoding="utf-8")
    rows: list[dict[str, Any]] = []
    raw_lines = destination.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(raw_lines):
      try:
        rows.append(json.loads(line))
      except json.JSONDecodeError:
        if index == len(raw_lines) - 1:
          break
        raise RuntimeError(f"corrupt optimization ledger line {index + 1}")
    if not rows or rows[0] != {"kind": "header", "identity": asdict(identity)}:
      raise RuntimeError("optimization ledger identity mismatch")
    completed: dict[str, dict[str, Any]] = {}
    for row in rows[1:]:
      if row.get("kind") == "complete":
        candidate_id = str(row["candidate_id"])
        if candidate_id in completed:
          raise RuntimeError(f"candidate completed more than once: {candidate_id}")
        completed[candidate_id] = dict(row["record"])
    return cls(destination, identity, completed)

  def _append(self, row: dict[str, Any]) -> None:
    encoded = canonical_json(row) + "\n"
    with self.path.open("a", encoding="utf-8") as handle:
      handle.write(encoded)
      handle.flush()
      os.fsync(handle.fileno())

  def reserve(self, candidate_id: str) -> bool:
    if not candidate_id:
      raise ValueError("candidate_id is required")
    if candidate_id in self._completed or candidate_id in self._reserved:
      return False
    self._append({"kind": "reserve", "candidate_id": candidate_id})
    self._reserved.add(candidate_id)
    return True

  def complete(self, candidate_id: str, record: dict[str, Any]) -> None:
    if candidate_id in self._completed:
      raise RuntimeError(f"candidate already completed: {candidate_id}")
    if candidate_id not in self._reserved:
      raise RuntimeError(f"candidate is not reserved: {candidate_id}")
    self._append({"kind": "complete", "candidate_id": candidate_id, "record": record})
    self._reserved.remove(candidate_id)
    self._completed[candidate_id] = dict(record)

  def completed_ids(self) -> set[str]:
    return set(self._completed)

  def completed_records(self) -> dict[str, dict[str, Any]]:
    return {candidate_id: dict(record) for candidate_id, record in self._completed.items()}
