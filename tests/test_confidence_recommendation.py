from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from carrot_sim.confidence_recommendation import RecommendationInputs, RecommendationPolicy, build_recommendation, write_report_bundle
from carrot_sim.sealed_holdout_revalidator import HoldoutResult


def holdout(deltas):
  return HoldoutResult("a"*64, tuple(sorted(deltas)), {}, deltas, min(deltas.values()) if deltas else None)


class ConfidenceRecommendationTests(unittest.TestCase):
  def setUp(self):
    self.policy = RecommendationPolicy(min_routes=3, bootstrap_samples=200, confidence_level=0.90, max_worst_route_degradation=-0.1)

  def test_three_state_truth_table(self):
    insufficient = build_recommendation(RecommendationInputs("c", holdout({"r1": 1.0}), True, False, "<x>"), self.policy)
    self.assertEqual(insufficient.state, "INSUFFICIENT_EVIDENCE")
    retained = build_recommendation(RecommendationInputs("c", holdout({"r1": -1.0, "r2": 0.1, "r3": 0.2}), True, True, "safe"), self.policy)
    self.assertEqual(retained.state, "RETAIN_CURRENT")
    candidate = build_recommendation(RecommendationInputs("c", holdout({"r1": 1.0, "r2": 1.1, "r3": 1.2}), True, True, "safe"), self.policy)
    self.assertEqual(candidate.state, "CONDITIONAL_CANDIDATE")

  def test_bootstrap_is_reproducible_and_authority_is_false(self):
    inputs = RecommendationInputs("c", holdout({"r1": 1.0, "r2": 1.1, "r3": 1.2}), True, True, "safe")
    first = build_recommendation(inputs, self.policy)
    second = build_recommendation(inputs, self.policy)
    self.assertEqual(first.confidence_interval, second.confidence_interval)
    self.assertFalse(first.deployment_authorized)
    self.assertFalse(first.real_vehicle_write)

  def test_report_bundle_is_finite_and_escapes_html(self):
    report = build_recommendation(RecommendationInputs("c", holdout({"r1": 1.0, "r2": 1.1, "r3": 1.2}), True, True, "<script>x</script>"), self.policy)
    with tempfile.TemporaryDirectory() as tmp:
      paths = write_report_bundle(report, Path(tmp))
      artifact = json.loads(paths["json"].read_text(), parse_constant=lambda value: self.fail(value))
      self.assertFalse(artifact["deployment_authorized"])
      html = paths["html"].read_text()
      self.assertNotIn("<script>x</script>", html)
      self.assertIn("&lt;script&gt;", html)
      self.assertIn("state,candidate_id", paths["csv"].read_text())


if __name__ == "__main__":
  unittest.main()
