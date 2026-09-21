from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from carrot_sim.optimization_campaign import OptimizationCampaign


class OptimizationCampaignTests(unittest.TestCase):
  def setUp(self):
    self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
    self.root = Path(self.tmp.name)
    self.settings = self.root / "settings.json"
    self.settings.write_text('{"LongActuatorDelay":20}', encoding="utf-8")

  def test_campaign_never_mutates_input_settings(self):
    before = self.settings.read_bytes()
    campaign = OptimizationCampaign.create(self.root/"campaign", "a"*64, self.settings, max_workers=2)
    campaign.advance("partition", {"routes": 10})
    self.assertEqual(self.settings.read_bytes(), before)
    self.assertFalse(campaign.status().real_vehicle_write)

  def test_resume_requires_exact_manifest(self):
    OptimizationCampaign.create(self.root/"campaign", "a"*64, self.settings, max_workers=2)
    with self.assertRaisesRegex(RuntimeError, "manifest"):
      OptimizationCampaign.resume(self.root/"campaign", "b"*64)

  def test_phase_order_and_blocked_reason(self):
    campaign = OptimizationCampaign.create(self.root/"campaign", "a"*64, self.settings, max_workers=2)
    with self.assertRaisesRegex(ValueError, "phase"):
      campaign.advance("simulate")
    campaign.advance("partition")
    campaign.block("MISSING_EVIDENCE")
    status = campaign.status()
    self.assertEqual(status.phase, "blocked")
    self.assertEqual(status.blocked_reason, "MISSING_EVIDENCE")

  def test_worker_limit_must_be_bounded(self):
    with self.assertRaisesRegex(ValueError, "workers"):
      OptimizationCampaign.create(self.root/"campaign", "a"*64, self.settings, max_workers=0)

  def test_cli_initializes_and_advances_without_mutating_settings(self):
    repo = Path(__file__).resolve().parents[1]
    output = self.root/"campaign"
    before = self.settings.read_bytes()
    base = [sys.executable, str(repo/"scripts/run_optimization_campaign.py"),
            "--output", str(output), "--manifest-hash", "a"*64]
    subprocess.run(base + ["--settings", str(self.settings), "--max-workers", "2"], cwd=repo, check=True)
    subprocess.run(base + ["--resume", "--phase", "partition"], cwd=repo, check=True)
    self.assertEqual(self.settings.read_bytes(), before)
    self.assertEqual(json.loads((output/"status.json").read_text())["phase"], "partition")


if __name__ == "__main__":
  unittest.main()
