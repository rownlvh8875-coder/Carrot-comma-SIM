import hashlib
import importlib
import importlib.util
import json
import unittest


RADAR_SHA = "22" * 32
CONFIG_SHA = "33" * 32
SERVICES = (
  "modelV2", "liveTracks", "carControl", "carState", "controlsState",
  "liveParameters", "radarState", "selfdriveState", "carrotMan",
)


def historical_snapshot_digest(row):
  payload = {
    "processEpoch": row["processEpoch"],
    "loopSequence": row["loopSequence"],
    "plannerCycle": row["plannerCycle"],
    "subMasterFrame": row["subMasterFrame"],
    "captureMonoTimeNs": row["captureMonoTimeNs"],
    "decisionMonoTimeNs": row["decisionMonoTimeNs"],
    "logMonoTimes": tuple(row[f"{service}LogMonoTime"] for service in SERVICES),
    "recvFrames": tuple(row[f"{service}RecvFrame"] for service in SERVICES),
    "recvTimesNs": tuple(row[f"{service}RecvTimeNs"] for service in SERVICES),
    "seenMask": row["seenMask"],
    "updatedMask": row["updatedMask"],
    "aliveMask": row["aliveMask"],
    "freqOkMask": row["freqOkMask"],
    "validMask": row["validMask"],
    "planningTriggerKind": row["planningTriggerKind"],
    "planningTriggerLogMonoTime": row["planningTriggerLogMonoTime"],
    "runLongitudinal": row["runLongitudinal"],
    "longitudinalPlanEmitted": row["longitudinalPlanEmitted"],
    "liveTracksRecent": row["liveTracksRecent"],
    "useLiveTracksTrigger": row["useLiveTracksTrigger"],
    "triggerIntervalOk": row["triggerIntervalOk"],
    "configSequence": row["configSequence"],
    "configSha256": row["configSha256"],
    "radarInputKind": row["radarInputKind"],
    "effectiveRadarStateSha256": row["effectiveRadarStateSha256"],
  }
  raw = json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
  ).encode("utf-8")
  return hashlib.sha256(raw).hexdigest()


def valid_trace_dict():
  row = {
    "schemaVersion": 6,
    "processEpoch": 1000000,
    "plannerCycle": 1,
    "subMasterFrame": 20,
    "planningTriggerKind": 0,
    "planningTriggerLogMonoTime": 1000,
    "configSequence": 1,
    "configSha256": CONFIG_SHA,
    "updatedMask": 0x1FF,
    "aliveMask": 0x1FF,
    "freqOkMask": 0x1FF,
    "validMask": 0x1FF,
    "radarInputKind": 0,
    "fastLeadMask": 1,
    "fastLeadTrackId": 7,
    "fastLeadReason": 1,
    "effectiveRadarStateSha256": RADAR_SHA,
    "loopSequence": 1,
    "captureMonoTimeNs": 123456700,
    "decisionMonoTimeNs": 123456800,
    "seenMask": 0x1FF,
    "longitudinalPlanEmitted": True,
    "runLongitudinal": True,
    "liveTracksRecent": True,
    "useLiveTracksTrigger": False,
    "triggerIntervalOk": True,
  }
  for index, service in enumerate(SERVICES):
    row[f"{service}LogMonoTime"] = 1000 + index
    row[f"{service}RecvFrame"] = 2000 + index
    row[f"{service}RecvTimeNs"] = 3000 + index
  row["consumedSnapshotIdentitySha256"] = historical_snapshot_digest(row)
  return row


def valid_config_dict():
  return {
    "schemaVersion": 6,
    "processEpoch": 1000000,
    "configSequence": 1,
    "configSha256": CONFIG_SHA,
    "canonicalJsonUtf8": "{}",
  }


class TestH1EvidenceParsing(unittest.TestCase):
  def _module(self):
    spec = importlib.util.find_spec("carrot_sim.h1_evidence")
    self.assertIsNotNone(spec, "carrot_sim.h1_evidence must exist")
    return importlib.import_module("carrot_sim.h1_evidence")

  def _config_verifier(self, module):
    verifier = getattr(module, "verify_config_snapshot", None)
    self.assertIsNotNone(verifier, "verify_config_snapshot must exist")
    return verifier

  def _trace_verifier(self, module):
    verifier = getattr(module, "verify_replay_trace", None)
    self.assertIsNotNone(verifier, "verify_replay_trace must exist")
    return verifier

  def test_rejects_unsupported_trace_schema(self):
    module = self._module()
    row = valid_trace_dict()
    row["schemaVersion"] = 7
    with self.assertRaisesRegex(module.H1EvidenceError, "unsupported H1 replay schema"):
      module.parse_replay_trace(row)

  def test_rejects_missing_snapshot_identity(self):
    module = self._module()
    row = valid_trace_dict()
    row.pop("consumedSnapshotIdentitySha256")
    with self.assertRaisesRegex(module.H1EvidenceError, "consumedSnapshotIdentitySha256"):
      module.parse_replay_trace(row)

  def test_rejects_missing_service_receive_identity(self):
    module = self._module()
    row = valid_trace_dict()
    row.pop("modelV2RecvFrame")
    with self.assertRaisesRegex(module.H1EvidenceError, "modelV2RecvFrame"):
      module.parse_replay_trace(row)

  def test_rejects_missing_loop_timing_identity(self):
    module = self._module()
    row = valid_trace_dict()
    row.pop("decisionMonoTimeNs")
    with self.assertRaisesRegex(module.H1EvidenceError, "decisionMonoTimeNs"):
      module.parse_replay_trace(row)

  def test_rejects_bool_for_integer_field(self):
    module = self._module()
    row = valid_trace_dict()
    row["loopSequence"] = True
    with self.assertRaisesRegex(module.H1EvidenceError, "loopSequence"):
      module.parse_replay_trace(row)

  def test_rejects_mask_outside_uint16(self):
    module = self._module()
    row = valid_trace_dict()
    row["seenMask"] = 1 << 16
    with self.assertRaisesRegex(module.H1EvidenceError, "seenMask"):
      module.parse_replay_trace(row)

  def test_complete_trace_groups_all_nine_service_identities(self):
    module = self._module()
    parsed = module.parse_replay_trace(valid_trace_dict())
    self.assertEqual(len(parsed.log_mono_times), 9)
    self.assertEqual(len(parsed.recv_frames), 9)
    self.assertEqual(len(parsed.recv_times_ns), 9)
    self.assertEqual(parsed.log_mono_times[0], 1000)
    self.assertEqual(parsed.recv_frames[-1], 2008)
    self.assertEqual(parsed.recv_times_ns[-1], 3008)

  def test_accepts_non_emitted_trace_with_empty_effective_identities(self):
    module = self._module()
    row = valid_trace_dict()
    row.update({
      "plannerCycle": 0,
      "configSequence": 0,
      "configSha256": "",
      "effectiveRadarStateSha256": "",
      "radarInputKind": 2,
      "fastLeadMask": 0,
      "fastLeadTrackId": -1,
      "fastLeadReason": 0,
      "longitudinalPlanEmitted": False,
      "runLongitudinal": False,
      "useLiveTracksTrigger": False,
    })
    row["consumedSnapshotIdentitySha256"] = historical_snapshot_digest(row)
    parsed = module.parse_replay_trace(row)
    self.assertFalse(parsed.longitudinal_plan_emitted)
    self.assertEqual(parsed.config_sha256, "")
    self.assertEqual(parsed.effective_radar_state_sha256, "")

  def test_replay_trace_integrity_accepts_exact_historical_identity(self):
    module = self._module()
    verifier = self._trace_verifier(module)
    verifier(module.parse_replay_trace(valid_trace_dict()))

  def test_replay_trace_integrity_rejects_snapshot_hash_mismatch(self):
    module = self._module()
    verifier = self._trace_verifier(module)
    row = valid_trace_dict()
    row["decisionMonoTimeNs"] += 1
    with self.assertRaisesRegex(module.H1EvidenceError, "snapshot identity mismatch"):
      verifier(module.parse_replay_trace(row))

  def test_replay_trace_integrity_rejects_trigger_timestamp_mismatch(self):
    module = self._module()
    verifier = self._trace_verifier(module)
    row = valid_trace_dict()
    row["planningTriggerLogMonoTime"] = row["liveTracksLogMonoTime"]
    row["consumedSnapshotIdentitySha256"] = historical_snapshot_digest(row)
    with self.assertRaisesRegex(module.H1EvidenceError, "planning trigger logMonoTime mismatch"):
      verifier(module.parse_replay_trace(row))

  def test_replay_trace_integrity_rejects_trigger_kind_mismatch(self):
    module = self._module()
    verifier = self._trace_verifier(module)
    row = valid_trace_dict()
    row["useLiveTracksTrigger"] = True
    row["consumedSnapshotIdentitySha256"] = historical_snapshot_digest(row)
    with self.assertRaisesRegex(module.H1EvidenceError, "planning trigger kind mismatch"):
      verifier(module.parse_replay_trace(row))

  def test_replay_trace_integrity_requires_run_for_emitted_plan(self):
    module = self._module()
    verifier = self._trace_verifier(module)
    row = valid_trace_dict()
    row["runLongitudinal"] = False
    row["consumedSnapshotIdentitySha256"] = historical_snapshot_digest(row)
    with self.assertRaisesRegex(module.H1EvidenceError, "emitted plan requires runLongitudinal"):
      verifier(module.parse_replay_trace(row))

  def test_replay_trace_integrity_requires_not_evaluated_radar_when_not_emitted(self):
    module = self._module()
    verifier = self._trace_verifier(module)
    row = valid_trace_dict()
    row.update({
      "longitudinalPlanEmitted": False,
      "runLongitudinal": False,
      "radarInputKind": 0,
      "effectiveRadarStateSha256": "",
    })
    row["consumedSnapshotIdentitySha256"] = historical_snapshot_digest(row)
    with self.assertRaisesRegex(module.H1EvidenceError, "non-emitted plan requires radarInputKind 2"):
      verifier(module.parse_replay_trace(row))

  def test_parses_config_snapshot_bytes(self):
    module = self._module()
    parsed = module.parse_config_snapshot(valid_config_dict())
    self.assertEqual(parsed.schema_version, 6)
    self.assertEqual(parsed.canonical_json_utf8, b"{}")

  def test_config_snapshot_hash_mismatch_is_rejected(self):
    module = self._module()
    verifier = self._config_verifier(module)
    row = valid_config_dict()
    row["configSha256"] = "00" * 32
    snapshot = module.parse_config_snapshot(row)
    with self.assertRaisesRegex(module.H1EvidenceError, "config hash mismatch"):
      verifier(snapshot)

  def test_config_snapshot_accepts_exact_canonical_json(self):
    module = self._module()
    verifier = self._config_verifier(module)
    payload = json.dumps(
      {"appliedConfig": {"tFollowGap1": 1.1}, "rawParams": {}},
      sort_keys=True,
      separators=(",", ":"),
      ensure_ascii=False,
      allow_nan=False,
    ).encode("utf-8")
    row = valid_config_dict()
    row["canonicalJsonUtf8"] = payload.decode("utf-8")
    row["configSha256"] = hashlib.sha256(payload).hexdigest()
    verifier(module.parse_config_snapshot(row))

  def test_config_snapshot_rejects_noncanonical_json_bytes(self):
    module = self._module()
    verifier = self._config_verifier(module)
    payload = b'{"rawParams": {}, "appliedConfig": {}}'
    row = valid_config_dict()
    row["canonicalJsonUtf8"] = payload.decode("utf-8")
    row["configSha256"] = hashlib.sha256(payload).hexdigest()
    with self.assertRaisesRegex(module.H1EvidenceError, "not canonical JSON"):
      verifier(module.parse_config_snapshot(row))


if __name__ == "__main__":
  unittest.main()
