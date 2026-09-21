from __future__ import annotations

import math
from typing import Any

MAX_PAGE_SIZE = 2000


class ReplayFrameError(ValueError):
  pass


def _finite(value: Any, field: str) -> float | None:
  if value is None:
    return None
  try:
    out = float(value)
  except (TypeError, ValueError) as exc:
    raise ReplayFrameError(f"invalid {field}") from exc
  if not math.isfinite(out):
    raise ReplayFrameError(f"non-finite {field}")
  return out


def _timestamp(value: Any) -> str:
  if isinstance(value, bool):
    raise ReplayFrameError("invalid timestamp")
  raw = str(value)
  if not raw.isdigit():
    raise ReplayFrameError("invalid timestamp")
  return raw


def normalize_frame(row: dict[str, Any], index: int) -> dict[str, Any]:
  if row.get("recommendation_authorized") is True or row.get("real_vehicle_write") is True:
    raise ReplayFrameError("unsafe authority")
  pose_values = [_finite(row.get(k), k) for k in
    ("post_pose_x_m", "post_pose_y_m", "post_heading_rad")]
  pose = None if any(v is None for v in pose_values) else dict(
    x_m=pose_values[0], y_m=pose_values[1], heading_rad=pose_values[2])
  lead_distance = _finite(row.get("lead_d_rel_m"), "lead_d_rel_m")
  lead = None if lead_distance is None else {
    "id": row.get("lead_id"), "distance_m": lead_distance,
    "relative_speed_mps": _finite(row.get("lead_v_rel_mps"), "lead_v_rel_mps"),
    "accel_mps2": _finite(row.get("lead_a_rel_mps2"), "lead_a_rel_mps2"),
  }
  lanes = row.get("lanes")
  if lanes is not None and not isinstance(lanes, dict):
    raise ReplayFrameError("invalid lanes")
  metrics = {
    "speed_mps": _finite(row.get("post_speed_mps"), "post_speed_mps"),
    "accel_mps2": _finite(row.get("post_accel_mps2"), "post_accel_mps2"),
    "jerk_mps3": _finite(row.get("jerk_mps3"), "jerk_mps3"),
    "steering": _finite(row.get("steering_angle_deg", row.get("lateral_command")), "steering"),
    "target_speed_mps": _finite(row.get("planner_v_target_mps"), "planner_v_target_mps"),
    "target_accel_mps2": _finite(row.get("planner_a_target_mps2"), "planner_a_target_mps2"),
    "ttc_s": _finite(row.get("ttc_s"), "ttc_s"),
  }
  return {
    "index": int(index), "mono_ns": _timestamp(row.get("step_ns", row.get("mono_ns"))),
    "elapsed_s": _finite(row.get("elapsed_s"), "elapsed_s"),
    "ego": {"pose": pose}, "lead": lead, "lanes": lanes,
    "metrics": metrics, "events": list(row.get("events") or []),
    "availability": {"pose": pose is not None, "lead": lead is not None,
      "lanes": lanes is not None},
    "authority": {"recommendation_authorized": False, "real_vehicle_write": False},
  }


def validate_frames(frames: list[dict[str, Any]]) -> dict[str, Any]:
  previous = None
  for frame in frames:
    now = int(_timestamp(frame["mono_ns"]))
    if previous is not None and now <= previous:
      raise ReplayFrameError("timestamps must be strictly increasing")
    previous = now
  return {"frame_count": len(frames), "valid": True}


def page_frames(frames: list[dict[str, Any]], offset: int, limit: int) -> dict[str, Any]:
  if offset < 0:
    raise ReplayFrameError("offset must be non-negative")
  if not 1 <= limit <= MAX_PAGE_SIZE:
    raise ReplayFrameError(f"limit must be 1..{MAX_PAGE_SIZE}")
  end = min(len(frames), offset + limit)
  return {"frames": frames[offset:end], "offset": offset,
    "next_offset": end if end < len(frames) else None, "total": len(frames)}



def _safe_authority(raw: dict[str, Any] | None) -> dict[str, bool]:
  data = raw or {}
  if data.get("recommendation_authorized") is True or data.get("real_vehicle_write") is True:
    raise ReplayFrameError("unsafe authority")
  return {"recommendation_authorized": False, "real_vehicle_write": False}


def load_visual_run(spec: dict[str, Any]) -> dict[str, Any]:
  import hashlib
  import json
  from pathlib import Path
  run_id = str(spec.get("run_id") or "")
  if not run_id or "/" in run_id or ".." in run_id:
    raise ReplayFrameError("invalid run_id")
  path = Path(str(spec.get("rows_path") or "")).resolve()
  try:
    raw = path.read_bytes()
  except OSError as exc:
    raise ReplayFrameError(f"missing rows: {path}") from exc
  expected = str(spec.get("rows_sha256") or "")
  if len(expected) != 64 or hashlib.sha256(raw).hexdigest() != expected:
    raise ReplayFrameError("rows SHA-256 mismatch")
  frames = []
  for index, line in enumerate(raw.decode("utf-8").splitlines()):
    if line.strip():
      frames.append(normalize_frame(json.loads(line), index))
  validate_frames(frames)
  return {"run_id": run_id, "label": str(spec.get("label") or run_id),
    "frame_count": len(frames), "frames": frames,
    "authority": _safe_authority(spec.get("authority")),
    "evidence_class": spec.get("evidence_class"),
    "rows_sha256": expected, "rows_path": str(path)}


def build_visual_catalog(specs: list[dict[str, Any]], *,
                         scenario_event_count: int) -> list[dict[str, Any]]:
  if isinstance(scenario_event_count, bool) or not isinstance(scenario_event_count, int) or scenario_event_count <= 0:
    raise ReplayFrameError("scenario_event_count must be a positive integer")
  seen: set[str] = set()
  out = []
  for spec in specs:
    run = load_visual_run(spec)
    if run["run_id"] in seen:
      raise ReplayFrameError(f"duplicate run_id: {run['run_id']}")
    seen.add(run["run_id"])
    out.append({k: run[k] for k in ("run_id", "label", "frame_count",
      "authority", "evidence_class", "rows_sha256")})
  return out



def compare_visual_runs(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
  safe = {"recommendation_authorized": False, "real_vehicle_write": False}
  for run in (baseline, candidate):
    authority = run.get("authority") or {}
    if authority.get("recommendation_authorized") is True or authority.get("real_vehicle_write") is True:
      return {"compatible": False, "reason": "UNSAFE_AUTHORITY",
        "paired_frames": [], "authority": safe}
  base_frames = list(baseline.get("frames") or [])
  candidate_frames = list(candidate.get("frames") or [])
  base_grid = [str(frame.get("mono_ns")) for frame in base_frames]
  candidate_grid = [str(frame.get("mono_ns")) for frame in candidate_frames]
  if base_grid != candidate_grid:
    return {"compatible": False, "reason": "TIME_GRID_MISMATCH",
      "paired_frames": [], "authority": safe}
  paired = [{"mono_ns": stamp, "baseline": base, "candidate": changed}
    for stamp, base, changed in zip(base_grid, base_frames, candidate_frames, strict=True)]
  return {"compatible": True, "reason": None, "paired_frames": paired,
    "authority": safe}
