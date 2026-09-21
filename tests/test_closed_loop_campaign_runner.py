from __future__ import annotations

import unittest

from carrot_sim.closed_loop_campaign_runner import (
  CampaignRunSpec,
  SimulationFrame,
  comparison_cache_key,
  run_comparison,
  validate_time_grid,
)


class ClosedLoopCampaignRunnerTests(unittest.TestCase):
  def spec(self, **changes):
    values = dict(manifest_hash="a"*64, scenario_hash="b"*64, params_hash="c"*64,
                  controller_hash="d"*64, plant_hash="e"*64, dt_s=0.01)
    values.update(changes)
    return CampaignRunSpec(**values)

  def test_time_grid_rejects_duplicate_and_gap(self):
    validate_time_grid((SimulationFrame(0.0), SimulationFrame(0.01), SimulationFrame(0.02)), 0.01)
    with self.assertRaisesRegex(ValueError, "strictly"):
      validate_time_grid((SimulationFrame(0.0), SimulationFrame(0.0)), 0.01)
    with self.assertRaisesRegex(ValueError, "grid"):
      validate_time_grid((SimulationFrame(0.0), SimulationFrame(0.02)), 0.01)

  def test_cache_key_changes_with_any_identity(self):
    base = self.spec()
    self.assertNotEqual(comparison_cache_key(base), comparison_cache_key(self.spec(plant_hash="f"*64)))

  def test_comparison_requires_identical_frame_times(self):
    baseline = (SimulationFrame(0.0), SimulationFrame(0.01))
    candidate = (SimulationFrame(0.0), SimulationFrame(0.02))
    with self.assertRaisesRegex(ValueError, "identical"):
      run_comparison(self.spec(), baseline, candidate, {"Delay": 1}, {"Delay": 1})

  def test_parameter_without_read_or_effect_is_unobservable(self):
    frames = (SimulationFrame(0.0, speed_mps=10.0), SimulationFrame(0.01, speed_mps=10.1))
    result = run_comparison(self.spec(), frames, frames, {"UnusedParam": 0}, {"UnusedParam": 1})
    coverage = result.parameter_coverage["UnusedParam"]
    self.assertFalse(coverage.observable)
    self.assertEqual(result.credited_changes, ())

  def test_read_parameter_with_trace_effect_is_credited(self):
    baseline = (SimulationFrame(0.0, speed_mps=10.0), SimulationFrame(0.01, speed_mps=10.0))
    candidate = (SimulationFrame(0.0, speed_mps=10.0), SimulationFrame(0.01, speed_mps=10.2, read_parameters=("Delay",)))
    result = run_comparison(self.spec(), baseline, candidate, {"Delay": 1}, {"Delay": 2})
    self.assertTrue(result.parameter_coverage["Delay"].observable)
    self.assertEqual(result.credited_changes, ("Delay",))


if __name__ == "__main__":
  unittest.main()
