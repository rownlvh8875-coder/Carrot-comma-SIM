from __future__ import annotations

import unittest

from carrot_sim.hybrid_scenario_world import HybridScenarioWorld, OverlayPolicy, SyntheticOverlay
from carrot_sim.recorded_scenario_world import RecordedScenarioWorld, RecordedWorldFrame
from carrot_sim.simulator_contract import VehicleState, WorldObservation


class HybridScenarioWorldTests(unittest.TestCase):
  def setUp(self):
    self.state = VehicleState(0.0, 10.0, 0.0)
    self.recorded = RecordedScenarioWorld([RecordedWorldFrame(0.0, road_curvature_1pm=0.01)])

  def test_radar_overlay_preserves_recorded_model_hash(self):
    overlay = SyntheticOverlay("radarState", WorldObservation(lead_present=True, lead_distance_m=20.0))
    world = HybridScenarioWorld(self.recorded, overlay, OverlayPolicy(("radarState",)), recorded_modelv2_sha256="a" * 64)
    observation = world.reset(self.state)
    self.assertTrue(observation.lead_present)
    self.assertEqual(observation.road_curvature_1pm, 0.01)
    receipt = world.overlay_receipt()
    self.assertEqual(receipt.before_modelv2_sha256, receipt.after_modelv2_sha256)
    self.assertFalse(receipt.real_vehicle_write)

  def test_unknown_overlay_is_rejected(self):
    overlay = SyntheticOverlay("modelV2", WorldObservation())
    with self.assertRaisesRegex(ValueError, "overlay"):
      HybridScenarioWorld(self.recorded, overlay, OverlayPolicy(("radarState",)), recorded_modelv2_sha256="a" * 64)

  def test_invalid_model_hash_is_rejected(self):
    with self.assertRaisesRegex(ValueError, "SHA-256"):
      HybridScenarioWorld(self.recorded, None, OverlayPolicy(("radarState",)), recorded_modelv2_sha256="bad")


if __name__ == "__main__":
  unittest.main()
