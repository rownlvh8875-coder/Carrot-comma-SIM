import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "integration" / "openpilot" / "h1_overlay_manifest.json"


class TestH1OverlayManifest(unittest.TestCase):
  def _load(self):
    self.assertTrue(MANIFEST.is_file(), "H1 overlay manifest must exist")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))

  def test_manifest_identity_is_frozen(self):
    data = self._load()
    self.assertEqual(data["schemaVersion"], 1)
    self.assertEqual(data["h1SchemaVersion"], 6)
    self.assertEqual(data["historicalSourceCommit"], "6383e0cda19f7d9bfeddb6a7732a6da764cca3da")
    self.assertEqual(data["historicalLiveBase"], "ce3d76301c988db8aa955e1ebc6496f0a0fd2abc")

  def test_required_paths_are_exactly_the_minimal_h1_surface(self):
    data = self._load()
    required = {entry["path"] for entry in data["paths"] if entry["classification"] == "REQUIRED"}
    self.assertEqual(required, {
      "openpilot/cereal/custom.capnp",
      "openpilot/cereal/log.capnp",
      "openpilot/cereal/services.py",
      "openpilot/selfdrive/carrot/carrot_functions.py",
      "openpilot/selfdrive/controls/lib/h1_observability.py",
      "openpilot/selfdrive/controls/lib/longitudinal_planner.py",
      "openpilot/selfdrive/controls/plannerd.py",
    })

  def test_overlay_paths_do_not_include_egpu_research_components(self):
    data = self._load()
    forbidden = ("egpu", "guardian", "shadow", "model_slot", "telemetry")
    for entry in data["paths"]:
      lower = entry["path"].lower()
      self.assertFalse(any(token in lower for token in forbidden), entry)
      self.assertIn(entry["classification"], {"REQUIRED", "OPTIONAL_RADAR_DECODE"})

  def test_radar_dbc_is_optional_not_control_authority(self):
    data = self._load()
    optional = [entry for entry in data["paths"] if entry["classification"] == "OPTIONAL_RADAR_DECODE"]
    self.assertEqual(optional, [{
      "path": "opendbc_repo/opendbc/dbc/generator/hyundai/hyundai_canfd_radar.dbc",
      "classification": "OPTIONAL_RADAR_DECODE",
    }])

  def test_historical_egpu_ci_is_explicitly_excluded(self):
    data = self._load()
    self.assertIn(".github/workflows/egpu-integrated-ci.yml", data["explicitlyExcludedHistoricalPaths"])


if __name__ == "__main__":
  unittest.main()
