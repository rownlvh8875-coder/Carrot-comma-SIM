import importlib
import importlib.util
import unittest

from carrot_sim.h1_evidence import H1ConfigSnapshot, H1ReplayTrace


CONFIG_A = "11" * 32
CONFIG_B = "22" * 32
RADAR = "33" * 32
SNAPSHOT = "44" * 32


def trace(*, loop=1, cycle=1, emitted=True, epoch=1000, config_sequence=1,
          config_sha=CONFIG_A, radar_sha=RADAR):
  return H1ReplayTrace(
    schema_version=6,
    process_epoch=epoch,
    planner_cycle=cycle,
    submaster_frame=loop,
    planning_trigger_kind=0,
    planning_trigger_log_mono_time=100000 + loop,
    config_sequence=config_sequence,
    config_sha256=config_sha,
    log_mono_times=tuple(1000 + i for i in range(9)),
    updated_mask=0x1FF,
    alive_mask=0x1FF,
    freq_ok_mask=0x1FF,
    valid_mask=0x1FF,
    radar_input_kind=0 if emitted else 2,
    fast_lead_mask=1 if emitted else 0,
    fast_lead_track_id=7 if emitted else -1,
    fast_lead_reason=1 if emitted else 0,
    effective_radar_state_sha256=radar_sha,
    loop_sequence=loop,
    capture_mono_time_ns=200000 + loop,
    decision_mono_time_ns=200100 + loop,
    seen_mask=0x1FF,
    longitudinal_plan_emitted=emitted,
    run_longitudinal=emitted,
    live_tracks_recent=True,
    use_live_tracks_trigger=False,
    trigger_interval_ok=True,
    recv_frames=tuple(2000 + i for i in range(9)),
    recv_times_ns=tuple(3000 + i for i in range(9)),
    consumed_snapshot_identity_sha256=SNAPSHOT,
  )


def config(*, sequence=1, sha=CONFIG_A, epoch=1000):
  return H1ConfigSnapshot(
    schema_version=6,
    process_epoch=epoch,
    config_sequence=sequence,
    config_sha256=sha,
    canonical_json_utf8=b"{}",
  )


class TestH1EvidenceSet(unittest.TestCase):
  def _qualify(self, traces, configs):
    spec = importlib.util.find_spec("carrot_sim.h1_evidence_set")
    self.assertIsNotNone(spec, "carrot_sim.h1_evidence_set must exist")
    module = importlib.import_module("carrot_sim.h1_evidence_set")
    return module.qualify_h1_evidence(traces, configs)

  def test_no_trace_holds(self):
    result = self._qualify([], [])
    self.assertEqual(result.status, "H1_HOLD")
    self.assertIn("NO_H1_TRACE", result.reasons)

  def test_gap_in_loop_sequence_holds(self):
    result = self._qualify(
      [trace(loop=1, cycle=1), trace(loop=3, cycle=2)],
      [config()],
    )
    self.assertEqual(result.status, "H1_HOLD")
    self.assertIn("LOOP_SEQUENCE_GAP", result.reasons)

  def test_mixed_process_epoch_holds(self):
    result = self._qualify(
      [trace(loop=1, cycle=1, epoch=1000), trace(loop=2, cycle=2, epoch=2000)],
      [config(epoch=1000), config(sequence=1, epoch=2000)],
    )
    self.assertIn("MIXED_PROCESS_EPOCH", result.reasons)

  def test_emitted_planner_cycle_must_increment_exactly_once(self):
    result = self._qualify(
      [trace(loop=1, cycle=1), trace(loop=2, cycle=3)],
      [config()],
    )
    self.assertIn("PLANNER_CYCLE_INVALID", result.reasons)

  def test_non_emitted_loop_may_keep_planner_cycle_constant(self):
    non_emitted = trace(loop=2, cycle=1, emitted=False, config_sequence=0, config_sha="", radar_sha="")
    result = self._qualify(
      [trace(loop=1, cycle=1), non_emitted, trace(loop=3, cycle=2)],
      [config()],
    )
    self.assertEqual(result.status, "H1_READY")

  def test_emitted_plan_requires_matching_config_snapshot(self):
    result = self._qualify([trace(config_sequence=4)], [])
    self.assertEqual(result.status, "H1_HOLD")
    self.assertIn("MISSING_CONFIG_SNAPSHOT", result.reasons)

  def test_config_identity_mismatch_holds(self):
    result = self._qualify(
      [trace(config_sequence=1, config_sha=CONFIG_A)],
      [config(sequence=1, sha=CONFIG_B)],
    )
    self.assertIn("CONFIG_IDENTITY_MISMATCH", result.reasons)

  def test_config_sequence_collision_holds(self):
    result = self._qualify(
      [trace(config_sequence=1, config_sha=CONFIG_A)],
      [config(sequence=1, sha=CONFIG_A), config(sequence=1, sha=CONFIG_B)],
    )
    self.assertIn("CONFIG_SEQUENCE_COLLISION", result.reasons)

  def test_missing_effective_identity_holds_even_for_constructed_record(self):
    malformed = trace(config_sha="", radar_sha="")
    result = self._qualify([malformed], [config()])
    self.assertIn("MISSING_EFFECTIVE_IDENTITY", result.reasons)

  def test_ready_evidence_reports_counts(self):
    result = self._qualify(
      [trace(loop=1, cycle=1), trace(loop=2, cycle=2)],
      [config()],
    )
    self.assertEqual(result.status, "H1_READY")
    self.assertEqual(result.reasons, ())
    self.assertEqual(result.trace_count, 2)
    self.assertEqual(result.planner_cycle_count, 2)
    self.assertEqual(result.config_count, 1)


if __name__ == "__main__":
  unittest.main()
