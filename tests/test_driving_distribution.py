from __future__ import annotations

import math
import unittest

from carrot_sim.driving_distribution import (
  DistributionConfig,
  FeatureRow,
  learn_distribution,
)


def row(route, speed, road="urban", band="fast", split="train"):
  return FeatureRow(
    route_id=route,
    features={"speed_mps": speed, "curvature_1pm": speed / 1000.0},
    strata={"road": road, "speed_band": band, "split": split},
    units={"speed_mps": "m/s", "curvature_1pm": "1/m"},
  )


class DrivingDistributionTests(unittest.TestCase):
  def setUp(self):
    self.config = DistributionConfig(
      min_stratum_count=3,
      quantiles=(0.1, 0.5, 0.9),
      fallback_order=(("road", "speed_band"), ("road",), ()),
      partition_hash="a" * 64,
    )

  def test_empirical_statistics_and_artifact_are_deterministic(self):
    rows = [row("r3", 30.0), row("r1", 10.0), row("r2", 20.0)]
    first = learn_distribution(rows, self.config)
    second = learn_distribution(reversed(rows), self.config)
    self.assertEqual(first.model_hash, second.model_hash)
    stats = first.strata["road=urban|speed_band=fast"].features["speed_mps"]
    self.assertEqual(stats.count, 3)
    self.assertEqual(stats.minimum, 10.0)
    self.assertEqual(stats.maximum, 30.0)
    self.assertEqual(stats.quantiles["0.5"], 20.0)

  def test_sparse_stratum_records_fallback(self):
    rows = [
      row("r1", 10.0, band="slow"),
      row("r2", 20.0, band="fast"),
      row("r3", 30.0, band="fast"),
      row("r4", 40.0, band="fast"),
    ]
    model = learn_distribution(rows, self.config)
    sparse = model.strata["road=urban|speed_band=slow"]
    self.assertEqual(sparse.fallback_level, "road")
    self.assertEqual(sparse.effective_count, 4)

  def test_holdout_and_search_validation_rows_are_rejected(self):
    for split in ("holdout", "search_validation"):
      with self.subTest(split=split), self.assertRaisesRegex(ValueError, "training partition"):
        learn_distribution([row("sealed", 10.0, split=split)], self.config)

  def test_nonfinite_and_unit_conflict_are_rejected(self):
    bad = row("r1", math.nan)
    with self.assertRaisesRegex(ValueError, "finite"):
      learn_distribution([bad], self.config)
    conflict = [
      row("r1", 10.0),
      FeatureRow("r2", {"speed_mps": 20.0}, {"road": "urban", "speed_band": "fast", "split": "train"}, {"speed_mps": "km/h"}),
    ]
    with self.assertRaisesRegex(ValueError, "unit"):
      learn_distribution(conflict, self.config)

  def test_transition_counts_follow_each_route_only(self):
    rows = [row("r1", 10.0, band="slow"), row("r1", 20.0, band="fast"), row("r2", 30.0, band="fast")]
    model = learn_distribution(rows, self.config)
    self.assertEqual(model.transitions["road=urban|speed_band=slow"]["road=urban|speed_band=fast"], 1)


if __name__ == "__main__":
  unittest.main()
