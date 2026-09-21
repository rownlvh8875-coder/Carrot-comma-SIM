from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from .campaign_manifest import canonical_json, content_sha256


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class HoldoutReceipt:
  campaign_hash: str
  finalist_ids: tuple[str, ...]
  purpose: str
  receipt_hash: str
  exposure_count: int
  real_vehicle_write: bool = False


@dataclass(frozen=True)
class PairedRouteResult:
  route_id: str
  baseline_times: tuple[float, ...]
  candidate_times: tuple[float, ...]
  baseline_metric: float
  candidate_metric: float
  safety_pass: bool


@dataclass(frozen=True)
class HoldoutResult:
  receipt_hash: str
  included_routes: tuple[str, ...]
  excluded_routes: dict[str, str]
  route_deltas: dict[str, float]
  worst_route_delta: float | None
  real_vehicle_write: bool = False


def open_holdout(
  receipt_path: str | Path,
  campaign_hash: str,
  finalist_ids: tuple[str, ...],
  *,
  purpose: str,
) -> HoldoutReceipt:
  if purpose != "revalidation":
    raise PermissionError("sealed holdout may be opened for revalidation only")
  if not _SHA256.fullmatch(campaign_hash):
    raise ValueError("campaign_hash must be lowercase SHA-256")
  finalists = tuple(sorted(set(finalist_ids)))
  if not finalists:
    raise ValueError("at least one finalist is required")
  identity = {"campaign_hash": campaign_hash, "finalist_ids": finalists, "purpose": purpose}
  receipt_hash = content_sha256(identity)
  destination = Path(receipt_path)
  if destination.exists():
    current = json.loads(destination.read_text(encoding="utf-8"))
    if current["campaign_hash"] != campaign_hash:
      raise RuntimeError("holdout campaign identity changed")
    if tuple(current["finalist_ids"]) != finalists:
      raise RuntimeError("holdout finalist set changed")
  else:
    destination.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
      **identity,
      "receipt_hash": receipt_hash,
      "real_vehicle_write": False,
    }
    destination.write_text(canonical_json(artifact) + "\n", encoding="utf-8")
  exposure_path = destination.with_suffix(destination.suffix + ".exposures.jsonl")
  with exposure_path.open("a", encoding="utf-8") as handle:
    handle.write(canonical_json({"receipt_hash": receipt_hash, "purpose": purpose}) + "\n")
  exposure_count = len(exposure_path.read_text(encoding="utf-8").splitlines())
  return HoldoutReceipt(campaign_hash, finalists, purpose, receipt_hash, exposure_count)


def revalidate(receipt: HoldoutReceipt, rows: tuple[PairedRouteResult, ...]) -> HoldoutResult:
  included: list[str] = []
  excluded: dict[str, str] = {}
  deltas: dict[str, float] = {}
  for row in sorted(rows, key=lambda item: item.route_id):
    if not row.baseline_times or not row.candidate_times:
      excluded[row.route_id] = "MISSING_PAIRED_FRAMES"
      continue
    if row.baseline_times != row.candidate_times:
      raise ValueError(f"route {row.route_id} does not have a paired time grid")
    if not row.safety_pass:
      excluded[row.route_id] = "SAFETY"
      continue
    included.append(row.route_id)
    deltas[row.route_id] = float(row.candidate_metric) - float(row.baseline_metric)
  worst = min(deltas.values()) if deltas else None
  return HoldoutResult(receipt.receipt_hash, tuple(included), excluded, deltas, worst)
