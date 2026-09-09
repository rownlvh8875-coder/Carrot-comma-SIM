from pathlib import Path
import unittest

from carrot_sim.h1_evidence_set import qualify_h1_evidence
from carrot_sim.h1_jsonl import load_h1_jsonl


ROOT = Path(__file__).resolve().parents[1]


class TestH1Examples(unittest.TestCase):
  def test_ready_example_is_ready(self):
    traces, configs = load_h1_jsonl(ROOT / "examples" / "h1_evidence_ready.jsonl")
    result = qualify_h1_evidence(traces, configs)
    self.assertEqual(result.status, "H1_READY")
    self.assertEqual(result.reasons, ())

  def test_missing_config_example_holds(self):
    traces, configs = load_h1_jsonl(ROOT / "examples" / "h1_evidence_missing_config.jsonl")
    result = qualify_h1_evidence(traces, configs)
    self.assertEqual(result.status, "H1_HOLD")
    self.assertIn("MISSING_CONFIG_SNAPSHOT", result.reasons)


if __name__ == "__main__":
  unittest.main()
