from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from carrot_sim.sealed_holdout_revalidator import PairedRouteResult, open_holdout, revalidate


class SealedHoldoutTests(unittest.TestCase):
  def setUp(self):
    self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
    self.path = Path(self.tmp.name) / "receipt.json"

  def test_changed_finalists_cannot_reopen_holdout(self):
    open_holdout(self.path, "a"*64, ("a",), purpose="revalidation")
    with self.assertRaisesRegex(RuntimeError, "finalist"):
      open_holdout(self.path, "a"*64, ("b",), purpose="revalidation")

  def test_learner_and_search_purpose_are_denied(self):
    for purpose in ("learning", "search"):
      with self.subTest(purpose=purpose), self.assertRaisesRegex(PermissionError, "revalidation"):
        open_holdout(self.path, "a"*64, ("a",), purpose=purpose)

  def test_same_finalists_reopen_same_receipt(self):
    first = open_holdout(self.path, "a"*64, ("b", "a"), purpose="revalidation")
    receipt_bytes = self.path.read_bytes()
    second = open_holdout(self.path, "a"*64, ("a", "b"), purpose="revalidation")
    self.assertEqual(first.receipt_hash, second.receipt_hash)
    self.assertEqual(second.exposure_count, 2)
    self.assertEqual(self.path.read_bytes(), receipt_bytes)

  def test_revalidation_requires_paired_time_grid(self):
    receipt = open_holdout(self.path, "a"*64, ("a",), purpose="revalidation")
    bad = PairedRouteResult("r1", (0.0, 0.01), (0.0, 0.02), 1.0, 2.0, True)
    with self.assertRaisesRegex(ValueError, "paired"):
      revalidate(receipt, (bad,))

  def test_missing_and_unsafe_routes_are_excluded(self):
    receipt = open_holdout(self.path, "a"*64, ("a",), purpose="revalidation")
    rows = (
      PairedRouteResult("r1", (0.0,), (0.0,), 1.0, 2.0, True),
      PairedRouteResult("r2", (), (), 1.0, 2.0, True),
      PairedRouteResult("r3", (0.0,), (0.0,), 1.0, 2.0, False),
    )
    result = revalidate(receipt, rows)
    self.assertEqual(result.included_routes, ("r1",))
    self.assertEqual(result.excluded_routes, {"r2": "MISSING_PAIRED_FRAMES", "r3": "SAFETY"})
    self.assertEqual(result.route_deltas["r1"], 1.0)


if __name__ == "__main__":
  unittest.main()
