from __future__ import annotations

import json
from pathlib import Path

import pytest


def base_row(ns: str = "1") -> dict:
  return {
    "step_ns": ns,
    "elapsed_s": 0.0,
    "post_speed_mps": 12.5,
    "recommendation_authorized": False,
    "real_vehicle_write": False,
  }


def test_exact_timestamp_and_missing_geometry_are_preserved():
  from carrot_sim.visual_replay_frames import normalize_frame
  frame = normalize_frame(base_row("9007199254740993"), 0)
  assert frame["mono_ns"] == "9007199254740993"
  assert frame["ego"]["pose"] is None
  assert frame["lead"] is None
  assert frame["lanes"] is None
  assert frame["availability"]["pose"] is False


def test_reversed_time_fails_closed():
  from carrot_sim.visual_replay_frames import ReplayFrameError, normalize_frame, validate_frames
  frames = [normalize_frame(base_row("2"), 0), normalize_frame(base_row("1"), 1)]
  with pytest.raises(ReplayFrameError, match="strictly increasing"):
    validate_frames(frames)


def test_unsafe_authority_fails_closed():
  from carrot_sim.visual_replay_frames import ReplayFrameError, normalize_frame
  row = base_row()
  row["recommendation_authorized"] = True
  with pytest.raises(ReplayFrameError, match="authority"):
    normalize_frame(row, 0)
def test_pages_are_bounded_and_report_next_offset():
  from carrot_sim.visual_replay_frames import normalize_frame, page_frames
  frames = []
  for i in range(3000):
    row = base_row(str(i + 1))
    row["elapsed_s"] = i * 0.05
    frames.append(normalize_frame(row, i))
  page = page_frames(frames, 1000, 500)
  assert len(page["frames"]) == 500
  assert page["next_offset"] == 1500
  assert page["total"] == 3000


def test_page_limit_over_2000_is_rejected():
  from carrot_sim.visual_replay_frames import ReplayFrameError, page_frames
  with pytest.raises(ReplayFrameError, match="limit"):
    page_frames([], 0, 2001)


def test_pose_lead_and_metrics_are_directly_mapped():
  from carrot_sim.visual_replay_frames import normalize_frame
  row = {**base_row(), "post_pose_x_m": 3.0, "post_pose_y_m": 2.5,
    "post_heading_rad": 0.1, "post_accel_mps2": -0.2,
    "planner_v_target_mps": 11.0, "planner_a_target_mps2": -0.3,
    "lead_d_rel_m": 22.0, "lead_v_rel_mps": -1.5}
  frame = normalize_frame(row, 0)
  assert frame["ego"]["pose"] == {"x_m": 3.0, "y_m": 2.5, "heading_rad": 0.1}
  assert frame["lead"]["distance_m"] == 22.0
  assert frame["metrics"]["target_speed_mps"] == 11.0


def saved_spec(tmp_path: Path) -> dict:
  rows = [
    {**base_row("1"), "elapsed_s": 0.0, "post_pose_x_m": 0,
      "post_pose_y_m": 0, "post_heading_rad": 0},
    {**base_row("2"), "elapsed_s": 0.05, "post_pose_x_m": 1,
      "post_pose_y_m": 2.5, "post_heading_rad": 0.1},
  ]
  path = tmp_path / "rows.jsonl"
  raw = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
  path.write_bytes(raw)
  import hashlib
  return {"run_id": "sample", "label": "샘플", "rows_path": str(path),
    "rows_sha256": hashlib.sha256(raw).hexdigest(),
    "authority": {"recommendation_authorized": False, "real_vehicle_write": False}}


def test_saved_run_adapter_preserves_pose_and_authority(tmp_path: Path):
  from carrot_sim.visual_replay_frames import load_visual_run
  run = load_visual_run(saved_spec(tmp_path))
  assert run["frame_count"] == 2
  assert run["frames"][-1]["ego"]["pose"]["y_m"] == pytest.approx(2.5)
  assert run["authority"]["real_vehicle_write"] is False


def test_hash_mismatch_rejects_run(tmp_path: Path):
  from carrot_sim.visual_replay_frames import ReplayFrameError, load_visual_run
  spec = saved_spec(tmp_path); spec["rows_sha256"] = "0" * 64
  with pytest.raises(ReplayFrameError, match="SHA-256"):
    load_visual_run(spec)


def test_catalog_accepts_any_positive_synthetic_count_and_rejects_nonpositive(tmp_path: Path):
  from carrot_sim.visual_replay_frames import ReplayFrameError, build_visual_catalog
  spec = saved_spec(tmp_path)
  assert build_visual_catalog([spec], scenario_event_count=6)[0]["run_id"] == "sample"
  for count in (0, -1):
    with pytest.raises(ReplayFrameError, match="positive"):
      build_visual_catalog([spec], scenario_event_count=count)
  with pytest.raises(ReplayFrameError, match="duplicate"):
    build_visual_catalog([spec, spec], scenario_event_count=6)


def test_catalog_metadata_does_not_embed_frames(tmp_path: Path):
  from carrot_sim.visual_replay_frames import build_visual_catalog
  catalog = build_visual_catalog([saved_spec(tmp_path)], scenario_event_count=6)
  assert catalog[0]["run_id"] == "sample"
  assert catalog[0]["frame_count"] == 2
  assert "frames" not in catalog[0]


def visual_run(timestamps, *, recommendation=False):
  frames=[]
  for i,stamp in enumerate(timestamps):
    frame=normalize_for_test(stamp,i)
    frames.append(frame)
  return {"frames":frames,"authority":{"recommendation_authorized":recommendation,
    "real_vehicle_write":False}}


def normalize_for_test(stamp,index):
  from carrot_sim.visual_replay_frames import normalize_frame
  row=base_row(stamp);row["elapsed_s"]=index*0.05
  return normalize_frame(row,index)


def test_comparison_pairs_exact_decimal_timestamps():
  from carrot_sim.visual_replay_frames import compare_visual_runs
  stamp="9007199254740993"
  result=compare_visual_runs(visual_run([stamp]),visual_run([stamp]))
  assert result["compatible"] is True
  assert result["paired_frames"][0]["mono_ns"]==stamp


def test_grid_mismatch_suppresses_deltas():
  from carrot_sim.visual_replay_frames import compare_visual_runs
  result=compare_visual_runs(visual_run(["1","2"]),visual_run(["1","3"]))
  assert result["compatible"] is False
  assert result["reason"]=="TIME_GRID_MISMATCH"
  assert result["paired_frames"]==[]


def test_authority_mismatch_suppresses_deltas():
  from carrot_sim.visual_replay_frames import compare_visual_runs
  result=compare_visual_runs(visual_run(["1"]),visual_run(["1"],recommendation=True))
  assert result["compatible"] is False
  assert result["reason"]=="UNSAFE_AUTHORITY"
