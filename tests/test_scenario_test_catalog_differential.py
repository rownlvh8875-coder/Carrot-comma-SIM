from __future__ import annotations

import math
import random
import unittest

from carrot_sim.scenario_test_catalog import (
  PrioritizedScenario, ScenarioPriorityFactors, ScenarioPriorityPolicy,
  ScenarioTestCase, prioritize_test_cases,
)


def previous_prioritize(cases, *, budget, policy=ScenarioPriorityPolicy()):
  """Frozen pre-optimization selection, used only as a differential oracle."""
  rows = list(cases)
  if budget <= 0:
    raise ValueError("budget must be > 0")
  if len({row.case_id for row in rows}) != len(rows):
    raise ValueError("case_id values must be unique")
  budget = min(budget, len(rows))
  selected = []
  covered = set()
  remaining = {row.case_id: row for row in rows}
  while remaining and len(selected) < budget:
    ranked = []
    for case in remaining.values():
      tags = set(case.coverage_tags)
      novelty = len(tags - covered) / len(tags) if tags else 0.0
      base = policy.base_score(case.priority)
      score = base + policy.novelty_bonus_weight * novelty
      ranked.append((score, base, novelty, case.case_id, case))
    ranked.sort(key=lambda row: (-row[0], -row[1], -row[2], row[3]))
    score, base, novelty, _, case = ranked[0]
    selected.append(PrioritizedScenario(case, base, novelty, score))
    covered.update(case.coverage_tags)
    del remaining[case.case_id]
  return tuple(selected)


def synthetic_cases(count: int, seed: int = 7301):
  rng = random.Random(seed)
  return [ScenarioTestCase(
    case_id=f"case-{index:05d}", scenario_id=f"synthetic-{index:05d}",
    objective="Synthetic catalog ordering fixture", inputs=("synthetic input",),
    steps=("select only",), platform="unit-test", expected_results=("deterministic order",),
    coverage_tags=tuple(f"tag-{i}" for i in rng.sample(range(96), rng.randrange(0, 17))),
    priority=ScenarioPriorityFactors(*(rng.choice((0.0, 0.25, 0.5, 0.75, 1.0)) for _ in range(4))),
  ) for index in range(count)]


class ScenarioCatalogDifferentialTests(unittest.TestCase):
  def test_deterministic_random_catalogs_match_previous_order_and_scores(self):
    policies = (ScenarioPriorityPolicy(), ScenarioPriorityPolicy(novelty_bonus_weight=0), ScenarioPriorityPolicy(criticality_weight=0.1, novelty_bonus_weight=2.0))
    for seed in range(6):
      cases = synthetic_cases(45, seed)
      random.Random(seed).shuffle(cases)
      for budget in (1, 7, 45, 60):
        for policy in policies:
          with self.subTest(seed=seed, budget=budget, policy=policy):
            self.assertEqual(prioritize_test_cases(iter(cases), budget=budget, policy=policy), previous_prioritize(cases, budget=budget, policy=policy))

  def test_ties_empty_tags_and_coverage_changes_match_previous(self):
    def case(case_id, tags):
      return ScenarioTestCase(case_id, case_id, "fixture", ("input",), ("step",), "unit-test", ("order",), tags, ScenarioPriorityFactors(.5, .5, .5, .5))
    cases = [case("z", ("common",)), case("b", ("common",)), case("a", ("new",)), case("none", ()), case("multi", ("new", "common"))]
    for ordering in (cases, list(reversed(cases))):
      for budget in (1, 3, 5):
        self.assertEqual(prioritize_test_cases(ordering, budget=budget), previous_prioritize(ordering, budget=budget))

  def test_empty_catalog_and_input_errors_are_preserved(self):
    self.assertEqual(prioritize_test_cases([], budget=1), ())
    cases = synthetic_cases(2)
    for rows, budget in ((cases, 0), (cases, -1), ([cases[0], cases[0]], 2)):
      with self.assertRaises(ValueError):
        prioritize_test_cases(rows, budget=budget)

  def test_overflowed_policy_keeps_original_stable_sort_order(self):
    cases = synthetic_cases(30)
    policy = ScenarioPriorityPolicy(exposure_weight=1e308, criticality_weight=1e308, complexity_weight=1e308, coverage_gap_weight=1e308)
    before = previous_prioritize(cases, budget=30, policy=policy)
    after = prioritize_test_cases(cases, budget=30, policy=policy)
    self.assertEqual([r.test_case.case_id for r in before], [r.test_case.case_id for r in after])
    for original, optimized in zip(before, after):
      for key in ("base_score", "novelty_fraction", "selection_score"):
        left, right = getattr(original, key), getattr(optimized, key)
        self.assertTrue(left == right or (math.isnan(left) and math.isnan(right)))


if __name__ == "__main__":
  unittest.main()
