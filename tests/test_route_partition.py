from __future__ import annotations

import unittest

from carrot_sim.route_partition import SplitRatios, build_route_partition


class RoutePartitionTests(unittest.TestCase):
  def test_partition_deduplicates_and_is_route_disjoint(self):
    part = build_route_partition(["r2", "r1", "r1"], "campaign-a", SplitRatios(70, 15, 15))
    self.assertEqual(set(part.assignments), {"r1", "r2"})
    part.assert_disjoint()
    self.assertEqual(part.manifest_hash, build_route_partition(["r1", "r2"], "campaign-a", SplitRatios(70, 15, 15)).manifest_hash)

  def test_ratio_total_must_be_one_hundred(self):
    with self.assertRaisesRegex(ValueError, "100"):
      SplitRatios(70, 20, 20)

  def test_blank_route_id_is_rejected(self):
    with self.assertRaisesRegex(ValueError, "route"):
      build_route_partition(["r1", ""], "campaign-a", SplitRatios(70, 15, 15))


if __name__ == "__main__":
  unittest.main()
