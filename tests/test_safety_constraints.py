from __future__ import annotations

import unittest

from carrot_sim.closed_loop_campaign_runner import CampaignRunSpec, SimulationFrame, run_comparison
from carrot_sim.safety_constraints import SafetyPolicy, evaluate_safety


def comparison(frames):
  spec = CampaignRunSpec("a"*64, "b"*64, "c"*64, "d"*64, "e"*64, 0.01)
  baseline = tuple(SimulationFrame(f.time_s, min_ttc_s=10.0, following_distance_m=30.0) for f in frames)
  return run_comparison(spec, baseline, tuple(frames), {}, {})


class SafetyConstraintTests(unittest.TestCase):
  def setUp(self):
    self.policy = SafetyPolicy(
      min_ttc_s=1.5,
      min_following_distance_m=2.0,
      min_accel_mps2=-4.0,
      max_abs_jerk_mps3=5.0,
      max_abs_steering_command=1.0,
      max_steering_saturation_frames=1,
      max_abs_lateral_error_m=0.5,
      max_abs_yaw_error_rad=0.2,
    )

  def test_safe_trace_is_eligible(self):
    run = comparison([SimulationFrame(0.0, min_ttc_s=3.0, following_distance_m=15.0)])
    self.assertTrue(evaluate_safety(run, self.policy).eligible)

  def test_missing_metric_fails_closed(self):
    run = comparison([SimulationFrame(0.0, min_ttc_s=None, following_distance_m=15.0)])
    decision = evaluate_safety(run, self.policy)
    self.assertFalse(decision.eligible)
    self.assertIn("MISSING_MIN_TTC", decision.reason_codes)

  def test_multiple_violations_are_all_preserved_in_fixed_order(self):
    run = comparison([
      SimulationFrame(0.0, accel_mps2=-5.0, jerk_mps3=7.0, min_ttc_s=1.0,
                      following_distance_m=1.0, steering_command=1.5,
                      lateral_error_m=0.8, yaw_error_rad=0.3, collision=True),
      SimulationFrame(0.01, min_ttc_s=1.0, following_distance_m=1.0, steering_command=1.5),
    ])
    decision = evaluate_safety(run, self.policy)
    self.assertFalse(decision.eligible)
    self.assertEqual(decision.reason_codes, (
      "COLLISION_PROXY", "MIN_TTC", "FOLLOWING_DISTANCE", "EXCESSIVE_DECEL",
      "EXCESSIVE_JERK", "STEERING_SATURATION", "LATERAL_DIVERGENCE", "YAW_DIVERGENCE",
    ))
    self.assertEqual(decision.first_failure_frame["COLLISION_PROXY"], 0)

  def test_boundary_equality_passes(self):
    run = comparison([SimulationFrame(0.0, accel_mps2=-4.0, jerk_mps3=5.0, min_ttc_s=1.5,
                                      following_distance_m=2.0, steering_command=1.0,
                                      lateral_error_m=0.5, yaw_error_rad=0.2)])
    self.assertTrue(evaluate_safety(run, self.policy).eligible)


if __name__ == "__main__":
  unittest.main()
