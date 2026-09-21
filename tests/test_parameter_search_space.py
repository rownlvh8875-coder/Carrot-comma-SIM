from __future__ import annotations

import unittest

from carrot_sim.parameter_search_space import ParameterAxis, SearchSpace


class ParameterSearchSpaceTests(unittest.TestCase):
  def test_axis_requires_valid_integer_grid(self):
    with self.assertRaises(ValueError):
      ParameterAxis("Delay", 30, 10, 5, "oat")
    with self.assertRaisesRegex(ValueError, "divide"):
      ParameterAxis("Delay", 10, 21, 5, "oat")
    with self.assertRaises(ValueError):
      ParameterAxis("Delay", 10, 20, 0, "oat")

  def test_search_space_cannot_widen_bounds(self):
    space = SearchSpace((ParameterAxis("LongActuatorDelay", 15, 30, 5, "oat"),))
    with self.assertRaisesRegex(ValueError, "bounds"):
      space.candidate({"LongActuatorDelay": 35})

  def test_oat_candidates_are_stable_and_skip_baseline(self):
    space = SearchSpace((
      ParameterAxis("B", 0, 2, 1, "oat"),
      ParameterAxis("A", 0, 2, 1, "oat"),
    ))
    candidates = space.oat_candidates({"A": 1, "B": 1}, active_axes={"A", "B"})
    self.assertEqual([row.changes for row in candidates], [
      {"A": 0}, {"A": 2}, {"B": 0}, {"B": 2},
    ])
    self.assertEqual(len({row.candidate_id for row in candidates}), 4)

  def test_inactive_axes_are_not_enumerated(self):
    space = SearchSpace((ParameterAxis("A", 0, 2, 1, "oat"), ParameterAxis("B", 0, 2, 1, "oat")))
    candidates = space.oat_candidates({"A": 1, "B": 1}, active_axes={"A"})
    self.assertTrue(all(set(row.changes) == {"A"} for row in candidates))

  def test_pairwise_interactions_use_only_active_axes(self):
    space = SearchSpace((ParameterAxis("A", 0, 2, 1, "interaction"), ParameterAxis("B", 0, 2, 1, "interaction")))
    rows = space.interaction_candidates({"A": 1, "B": 1}, active_axes={"A", "B"})
    self.assertTrue(rows)
    self.assertTrue(all(set(row.changes) == {"A", "B"} for row in rows))


if __name__ == "__main__":
  unittest.main()
