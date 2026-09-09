from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


H1_SCHEMA_VERSION = 6
_HEX = frozenset("0123456789abcdefABCDEF")


class H1EvidenceError(ValueError):
  """Raised when normalized H1 evidence violates the replay contract."""


@dataclass(frozen=True)
class H1ReplayTrace:
  schema_version: int
  process_epoch: int
  loop_sequence: int
  planner_cycle: int
  submaster_frame: int
  planning_trigger_kind: int
  planning_trigger_log_mono_time: int
  config_sequence: int
  config_sha256: str
  radar_input_kind: int
  effective_radar_state_sha256: str
  consumed_snapshot_identity_sha256: str
  run_longitudinal: bool
  longitudinal_plan_emitted: bool


@dataclass(frozen=True)
class H1ConfigSnapshot:
  schema_version: int
  process_epoch: int
  config_sequence: int
  config_sha256: str
  canonical_json_utf8: bytes


def _required(row: dict[str, Any], name: str) -> Any:
  if name not in row:
    raise H1EvidenceError(f"missing required field: {name}")
  return row[name]


def _int_field(row: dict[str, Any], name: str) -> int:
  value = _required(row, name)
  if isinstance(value, bool) or not isinstance(value, int):
    raise H1EvidenceError(f"{name} must be an integer")
  return value


def _bool_field(row: dict[str, Any], name: str) -> bool:
  value = _required(row, name)
  if not isinstance(value, bool):
    raise H1EvidenceError(f"{name} must be a boolean")
  return value


def _sha_field(row: dict[str, Any], name: str, *, allow_empty: bool = False) -> str:
  value = _required(row, name)
  if not isinstance(value, str):
    raise H1EvidenceError(f"{name} must be a hex string")
  if value == "" and allow_empty:
    return ""
  if len(value) != 64 or any(ch not in _HEX for ch in value):
    raise H1EvidenceError(f"{name} must be exactly 64 hexadecimal characters")
  return value.lower()


def _schema(row: dict[str, Any], *, kind: str) -> int:
  version = _int_field(row, "schemaVersion")
  if version != H1_SCHEMA_VERSION:
    raise H1EvidenceError(f"unsupported H1 {kind} schema: {version}")
  return version


def parse_replay_trace(row: dict[str, Any]) -> H1ReplayTrace:
  if not isinstance(row, dict):
    raise H1EvidenceError("H1 replay trace must be an object")

  schema_version = _schema(row, kind="replay")
  emitted = _bool_field(row, "longitudinalPlanEmitted")
  trigger_kind = _int_field(row, "planningTriggerKind")
  if trigger_kind not in (0, 1):
    raise H1EvidenceError("planningTriggerKind must be 0 or 1")
  radar_input_kind = _int_field(row, "radarInputKind")
  if radar_input_kind not in (0, 1, 2):
    raise H1EvidenceError("radarInputKind must be 0, 1, or 2")

  config_sha = _sha_field(row, "configSha256", allow_empty=not emitted)
  radar_sha = _sha_field(row, "effectiveRadarStateSha256", allow_empty=not emitted)
  if emitted and (not config_sha or not radar_sha):
    raise H1EvidenceError("emitted plan requires config and effective radar identities")

  return H1ReplayTrace(
    schema_version=schema_version,
    process_epoch=_int_field(row, "processEpoch"),
    loop_sequence=_int_field(row, "loopSequence"),
    planner_cycle=_int_field(row, "plannerCycle"),
    submaster_frame=_int_field(row, "subMasterFrame"),
    planning_trigger_kind=trigger_kind,
    planning_trigger_log_mono_time=_int_field(row, "planningTriggerLogMonoTime"),
    config_sequence=_int_field(row, "configSequence"),
    config_sha256=config_sha,
    radar_input_kind=radar_input_kind,
    effective_radar_state_sha256=radar_sha,
    consumed_snapshot_identity_sha256=_sha_field(row, "consumedSnapshotIdentitySha256"),
    run_longitudinal=_bool_field(row, "runLongitudinal"),
    longitudinal_plan_emitted=emitted,
  )


def parse_config_snapshot(row: dict[str, Any]) -> H1ConfigSnapshot:
  if not isinstance(row, dict):
    raise H1EvidenceError("H1 config snapshot must be an object")

  payload = _required(row, "canonicalJsonUtf8")
  if isinstance(payload, str):
    payload_bytes = payload.encode("utf-8")
  elif isinstance(payload, bytes):
    payload_bytes = payload
  else:
    raise H1EvidenceError("canonicalJsonUtf8 must be UTF-8 text or bytes")

  return H1ConfigSnapshot(
    schema_version=_schema(row, kind="config"),
    process_epoch=_int_field(row, "processEpoch"),
    config_sequence=_int_field(row, "configSequence"),
    config_sha256=_sha_field(row, "configSha256"),
    canonical_json_utf8=payload_bytes,
  )


def verify_config_snapshot(snapshot: H1ConfigSnapshot) -> None:
  digest = hashlib.sha256(snapshot.canonical_json_utf8).hexdigest()
  if digest != snapshot.config_sha256:
    raise H1EvidenceError("config hash mismatch")

  try:
    decoded = json.loads(snapshot.canonical_json_utf8.decode("utf-8"))
    canonical = json.dumps(
      decoded,
      sort_keys=True,
      separators=(",", ":"),
      ensure_ascii=False,
      allow_nan=False,
    ).encode("utf-8")
  except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
    raise H1EvidenceError("invalid config canonical JSON") from exc

  if canonical != snapshot.canonical_json_utf8:
    raise H1EvidenceError("config payload is not canonical JSON")
