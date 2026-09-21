from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unittest

from carrot_sim.optimization_ledger import LedgerIdentity, OptimizationLedger


def identity(suffix="a"):
  return LedgerIdentity(*(suffix * 64 for _ in range(8)))


class OptimizationLedgerTests(unittest.TestCase):
  def setUp(self):
    self.tmp = tempfile.TemporaryDirectory()
    self.addCleanup(self.tmp.cleanup)
    self.path = Path(self.tmp.name) / "run.jsonl"

  def test_mismatched_identity_rejects_resume(self):
    OptimizationLedger.open(self.path, identity("a"))
    with self.assertRaisesRegex(RuntimeError, "identity"):
      OptimizationLedger.open(self.path, identity("b"))

  def test_reserve_complete_and_resume(self):
    ledger = OptimizationLedger.open(self.path, identity())
    self.assertTrue(ledger.reserve("c1"))
    self.assertFalse(ledger.reserve("c1"))
    ledger.complete("c1", {"score": 1.0})
    self.assertEqual(ledger.completed_ids(), {"c1"})
    resumed = OptimizationLedger.open(self.path, identity())
    self.assertEqual(resumed.completed_ids(), {"c1"})

  def test_abandoned_reservation_can_be_recovered(self):
    ledger = OptimizationLedger.open(self.path, identity())
    ledger.reserve("c1")
    resumed = OptimizationLedger.open(self.path, identity())
    self.assertTrue(resumed.reserve("c1"))

  def test_duplicate_completion_is_rejected(self):
    ledger = OptimizationLedger.open(self.path, identity())
    ledger.reserve("c1")
    ledger.complete("c1", {"score": 1.0})
    with self.assertRaisesRegex(RuntimeError, "completed"):
      ledger.complete("c1", {"score": 2.0})

  def test_nonfinite_record_is_rejected(self):
    ledger = OptimizationLedger.open(self.path, identity())
    ledger.reserve("c1")
    with self.assertRaisesRegex(ValueError, "finite"):
      ledger.complete("c1", {"score": math.inf})

  def test_truncated_final_line_is_ignored_on_resume(self):
    ledger = OptimizationLedger.open(self.path, identity())
    ledger.reserve("c1")
    with self.path.open("ab") as handle:
      handle.write(b'{"kind":"complete"')
    resumed = OptimizationLedger.open(self.path, identity())
    self.assertTrue(resumed.reserve("c1"))


if __name__ == "__main__":
  unittest.main()
