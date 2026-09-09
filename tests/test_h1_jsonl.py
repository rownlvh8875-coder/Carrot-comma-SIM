import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from carrot_sim.h1_evidence import H1EvidenceError


RADAR_SHA = "55" * 32
SNAPSHOT_SHA = "66" * 32
SERVICES = (
  "modelV2", "liveTracks", "carControl", "carState", "controlsState",
  "liveParameters", "radarState", "selfdriveState", "carrotMan",
)
ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "inspect_h1_evidence.py"


def config_payload():
  return json.dumps(
    {"appliedConfig": {"tFollowGap1": 1.1}, "rawParams": {}},
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
  ).encode("utf-8")


def valid_config_dict():
  payload = config_payload()
  return {
    "schemaVersion": 6,
    "processEpoch": 1000,
    "configSequence": 1,
    "configSha256": hashlib.sha256(payload).hexdigest(),
    "canonicalJsonUtf8": payload.decode("utf-8"),
  }


def valid_trace_dict():
  config_sha = valid_config_dict()["configSha256"]
  row = {
    "schemaVersion": 6,
    "processEpoch": 1000,
    "plannerCycle": 1,
    "subMasterFrame": 10,
    "planningTriggerKind": 0,
    "planningTriggerLogMonoTime": 123456,
    "configSequence": 1,
    "configSha256": config_sha,
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
    "captureMonoTimeNs": 123400,
    "decisionMonoTimeNs": 123500,
    "seenMask": 0x1FF,
    "longitudinalPlanEmitted": True,
    "runLongitudinal": True,
    "liveTracksRecent": True,
    "useLiveTracksTrigger": False,
    "triggerIntervalOk": True,
    "consumedSnapshotIdentitySha256": SNAPSHOT_SHA,
  }
  for index, service in enumerate(SERVICES):
    row[f"{service}LogMonoTime"] = 1000 + index
    row[f"{service}RecvFrame"] = 2000 + index
    row[f"{service}RecvTimeNs"] = 3000 + index
  return row


class TestH1Jsonl(unittest.TestCase):
  def _module(self):
    spec = importlib.util.find_spec("carrot_sim.h1_jsonl")
    self.assertIsNotNone(spec, "carrot_sim.h1_jsonl must exist")
    return importlib.import_module("carrot_sim.h1_jsonl")

  def _write(self, rows):
    td = tempfile.TemporaryDirectory()
    path = Path(td.name) / "h1.jsonl"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return td, path

  def _run_cli(self, path):
    return subprocess.run(
      [sys.executable, str(CLI), str(path)],
      cwd=ROOT,
      capture_output=True,
      text=True,
      check=False,
    )

  def test_loads_trace_and_verified_config_records(self):
    module = self._module()
    td, path = self._write([
      json.dumps({"type": "carrotH1ConfigSnapshot", "data": valid_config_dict()}),
      json.dumps({"type": "carrotH1ReplayTrace", "data": valid_trace_dict()}),
    ])
    self.addCleanup(td.cleanup)
    traces, configs = module.load_h1_jsonl(path)
    self.assertEqual(len(traces), 1)
    self.assertEqual(len(configs), 1)

  def test_blank_lines_are_ignored(self):
    module = self._module()
    td, path = self._write([
      "",
      json.dumps({"type": "carrotH1ConfigSnapshot", "data": valid_config_dict()}),
      "   ",
      json.dumps({"type": "carrotH1ReplayTrace", "data": valid_trace_dict()}),
    ])
    self.addCleanup(td.cleanup)
    traces, configs = module.load_h1_jsonl(path)
    self.assertEqual((len(traces), len(configs)), (1, 1))

  def test_malformed_json_reports_one_based_line_number(self):
    module = self._module()
    td, path = self._write(["", "{not json}"])
    self.addCleanup(td.cleanup)
    with self.assertRaisesRegex(H1EvidenceError, "line 2"):
      module.load_h1_jsonl(path)

  def test_unknown_record_type_is_rejected(self):
    module = self._module()
    td, path = self._write([json.dumps({"type": "other", "data": {}})])
    self.addCleanup(td.cleanup)
    with self.assertRaisesRegex(H1EvidenceError, "unknown H1 record type"):
      module.load_h1_jsonl(path)

  def test_missing_data_is_rejected(self):
    module = self._module()
    td, path = self._write([json.dumps({"type": "carrotH1ReplayTrace"})])
    self.addCleanup(td.cleanup)
    with self.assertRaisesRegex(H1EvidenceError, "missing data"):
      module.load_h1_jsonl(path)

  def test_invalid_config_hash_is_rejected_during_load(self):
    module = self._module()
    row = valid_config_dict()
    row["configSha256"] = "00" * 32
    td, path = self._write([json.dumps({"type": "carrotH1ConfigSnapshot", "data": row})])
    self.addCleanup(td.cleanup)
    with self.assertRaisesRegex(H1EvidenceError, "config hash mismatch"):
      module.load_h1_jsonl(path)

  def test_cli_returns_zero_and_ready_summary_for_complete_evidence(self):
    td, path = self._write([
      json.dumps({"type": "carrotH1ConfigSnapshot", "data": valid_config_dict()}),
      json.dumps({"type": "carrotH1ReplayTrace", "data": valid_trace_dict()}),
    ])
    self.addCleanup(td.cleanup)
    result = self._run_cli(path)
    self.assertEqual(result.returncode, 0, result.stderr)
    summary = json.loads(result.stdout)
    self.assertEqual(summary["status"], "H1_READY")
    self.assertEqual(summary["traceCount"], 1)
    self.assertEqual(summary["plannerCycleCount"], 1)
    self.assertEqual(summary["configCount"], 1)

  def test_cli_returns_two_for_structurally_valid_hold(self):
    td, path = self._write([])
    self.addCleanup(td.cleanup)
    result = self._run_cli(path)
    self.assertEqual(result.returncode, 2, result.stderr)
    summary = json.loads(result.stdout)
    self.assertEqual(summary["status"], "H1_HOLD")
    self.assertIn("NO_H1_TRACE", summary["reasons"])

  def test_cli_returns_three_for_malformed_evidence(self):
    td, path = self._write(["{not json}"])
    self.addCleanup(td.cleanup)
    result = self._run_cli(path)
    self.assertEqual(result.returncode, 3)
    summary = json.loads(result.stdout)
    self.assertEqual(summary["status"], "H1_ERROR")
    self.assertIn("line 1", summary["error"])


if __name__ == "__main__":
  unittest.main()
