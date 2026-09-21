from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from carrot_sim.campaign_manifest import canonical_json
from carrot_sim.driving_distribution import DistributionConfig, FeatureRow, learn_distribution
from carrot_sim.learned_scenario_generator import (
  ScenarioGeneratorConfig,
  generate_scenario,
  generate_scenario_pack,
)
from carrot_sim.scenario_parameterization import LogicalScenarioTemplate, ParameterRange


def distribution():
  rows = [
    FeatureRow(
      f"r{i}",
      {"speed_mps": float(10 + i), "curvature_1pm": float(i) / 1000.0},
      {"road": "urban", "speed_band": "medium", "split": "train"},
      {"speed_mps": "m/s", "curvature_1pm": "1/m"},
    )
    for i in range(4)
  ]
  config = DistributionConfig(2, (0.1, 0.5, 0.9), (("road", "speed_band"), ("road",), ()), "a" * 64)
  return learn_distribution(rows, config)


class LearnedScenarioGeneratorTests(unittest.TestCase):
  def test_generation_is_reproducible_and_unauthorized(self):
    model = distribution()
    config = ScenarioGeneratorConfig(("lead_hard_brake", "stop_and_go"))
    first = generate_scenario(model, config, "seed-a", 7)
    second = generate_scenario(model, config, "seed-a", 7)
    self.assertEqual(canonical_json(first.to_artifact()), canonical_json(second.to_artifact()))
    self.assertFalse(first.parameter_tuning_authorized)
    self.assertFalse(first.real_route_acceptance_eligible)
    self.assertEqual(first.evidence_role, "synthetic_search")

  def test_normal_samples_remain_inside_learned_support(self):
    model = distribution()
    config = ScenarioGeneratorConfig(("lead_hard_brake",))
    scenario = generate_scenario(model, config, "seed", 0)
    support = model.strata[scenario.stratum].features
    for name, value in scenario.parameters.items():
      self.assertGreaterEqual(value, support[name].minimum)
      self.assertLessEqual(value, support[name].maximum)
      self.assertFalse(scenario.sampled_values[name]["out_of_distribution"])

  def test_boundary_stress_is_explicitly_out_of_distribution(self):
    scenario = generate_scenario(
      distribution(),
      ScenarioGeneratorConfig(("curve_follow_brake",), boundary_stress_every=1, tail_expansion_fraction=0.05),
      "seed",
      0,
    )
    self.assertEqual(scenario.evidence_role, "synthetic_stress")
    self.assertTrue(scenario.out_of_distribution)
    self.assertTrue(any(item["out_of_distribution"] for item in scenario.sampled_values.values()))

  def test_pack_deduplicates_by_content_hash_and_caps_strata(self):
    pack = generate_scenario_pack(
      distribution(),
      ScenarioGeneratorConfig(("lead_hard_brake",), max_per_stratum=2),
      "seed",
      10,
    )
    self.assertEqual(len(pack), 2)
    self.assertEqual(len({row.content_hash for row in pack}), 2)

  def test_existing_logical_template_carries_no_tuning_authority(self):
    sample = LogicalScenarioTemplate("x", (ParameterRange("speed", 0.0, 1.0),)).sample(0)
    self.assertFalse(sample.evidence.metadata["parameter_tuning_authorized"])

  def test_cli_writes_reproducible_canonical_jsonl(self):
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmp:
      model_path = Path(tmp) / "model.json"
      model_path.write_text(canonical_json(distribution().to_artifact()), encoding="utf-8")
      outputs = [Path(tmp) / "a.jsonl", Path(tmp) / "b.jsonl"]
      for output in outputs:
        subprocess.run([
          sys.executable, str(root / "scripts/build_learned_scenario_pack.py"),
          "--model", str(model_path), "--output", str(output),
          "--seed", "fixed", "--count", "3", "--families", "lead_hard_brake,stop_and_go",
        ], cwd=root, check=True)
      self.assertEqual(outputs[0].read_bytes(), outputs[1].read_bytes())
      rows = [json.loads(line) for line in outputs[0].read_text().splitlines()]
      self.assertEqual(len(rows), 3)
      self.assertTrue(all(not row["parameter_tuning_authorized"] for row in rows))


if __name__ == "__main__":
  unittest.main()
