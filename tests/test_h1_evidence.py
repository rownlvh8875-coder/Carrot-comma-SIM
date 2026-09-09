import hashlib
import importlib
import importlib.util
import json
import unittest


TRACE_SHA = "11" * 32
RADAR_SHA = "22" * 32
CONFIG_SHA = "33" * 32


def valid_trace_dict():
  return {
    "schemaVersion": 6,
    "processEpoch": 1000000,
    "loopSequence": 1,
    "plannerCycle": 1,
    "subMasterFrame": 20,
    "planningTriggerKind": 0,
    "planningTriggerLogMonoTime": 123456789,
    "configSequence": 1,
    "configSha256": CONFIG_SHA,
    "radarInputKind": 0,
    "effectiveRadarStateSha256": RADAR_SHA,
    "consumedSnapshotIdentitySha256": TRACE_SHA,
    "runLongitudinal": True,
    "longitudinalPlanEmitted": True,
  }


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

  def _verifier(self, module):
    verifier = getattr(module, "verify_config_snapshot", None)
    self.assertIsNotNone(verifier, "verify_config_snapshot must exist")
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

  def test_rejects_bool_for_integer_field(self):
    module = self._module()
    row = valid_trace_dict()
    row["loopSequence"] = True
    with self.assertRaisesRegex(module.H1EvidenceError, "loopSequence"):
      module.parse_replay_trace(row)

  def test_accepts_non_emitted_trace_with_empty_effective_identities(self):
    module = self._module()
    row = valid_trace_dict()
    row.update({
      "plannerCycle": 0,
      "configSequence": 0,
      "configSha256": "",
      "effectiveRadarStateSha256": "",
      "radarInputKind": 2,
      "longitudinalPlanEmitted": False,
      "runLongitudinal": False,
    })
    parsed = module.parse_replay_trace(row)
    self.assertFalse(parsed.longitudinal_plan_emitted)
    self.assertEqual(parsed.config_sha256, "")
    self.assertEqual(parsed.effective_radar_state_sha256, "")

  def test_parses_config_snapshot_bytes(self):
    module = self._module()
    parsed = module.parse_config_snapshot(valid_config_dict())
    self.assertEqual(parsed.schema_version, 6)
    self.assertEqual(parsed.canonical_json_utf8, b"{}")

  def test_config_snapshot_hash_mismatch_is_rejected(self):
    module = self._module()
    verifier = self._verifier(module)
    row = valid_config_dict()
    row["configSha256"] = "00" * 32
    snapshot = module.parse_config_snapshot(row)
    with self.assertRaisesRegex(module.H1EvidenceError, "config hash mismatch"):
      verifier(snapshot)

  def test_config_snapshot_accepts_exact_canonical_json(self):
    module = self._module()
    verifier = self._verifier(module)
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
    verifier = self._verifier(module)
    payload = b'{"rawParams": {}, "appliedConfig": {}}'
    row = valid_config_dict()
    row["canonicalJsonUtf8"] = payload.decode("utf-8")
    row["configSha256"] = hashlib.sha256(payload).hexdigest()
    with self.assertRaisesRegex(module.H1EvidenceError, "not canonical JSON"):
      verifier(module.parse_config_snapshot(row))


if __name__ == "__main__":
  unittest.main()
