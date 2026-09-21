from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from carrot_sim.constrained_parameter_optimizer import CandidateEvaluation, OptimizerConfig, run_search
from carrot_sim.optimization_ledger import LedgerIdentity, OptimizationLedger
from carrot_sim.parameter_search_space import ParameterCandidate


def identity():
  return LedgerIdentity(*("a"*64 for _ in range(8)))


class ConstrainedOptimizerTests(unittest.TestCase):
  def candidates(self):
    return (
      ParameterCandidate({"A": 0}, "a", "oat"),
      ParameterCandidate({"A": 1}, "b", "oat"),
      ParameterCandidate({"A": 2}, "c", "oat"),
    )

  def run_optimizer(self, evaluator, budget=3):
    tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
    ledger = OptimizationLedger.open(Path(tmp.name)/"run.jsonl", identity())
    return run_search(self.candidates(), ledger, evaluator, OptimizerConfig(("gain", "worst"), {"worst": 0.0}, budget))

  def test_unsafe_and_unobservable_candidates_never_reach_frontier(self):
    def evaluate(candidate):
      return CandidateEvaluation(candidate.candidate_id, {"gain": 2.0, "worst": 0.0},
                                 safe=candidate.candidate_id != "a",
                                 observable=candidate.candidate_id != "b")
    result = self.run_optimizer(evaluate)
    self.assertEqual(result.pareto_frontier, ("c",))
    self.assertEqual(result.excluded, {"a": "SAFETY", "b": "UNOBSERVABLE"})
    self.assertIsNone(result.aggregate_winner)

  def test_worst_case_constraint_excludes_mean_gain(self):
    def evaluate(candidate):
      return CandidateEvaluation(candidate.candidate_id, {"gain": 10.0, "worst": 1.0}, True, True)
    result = self.run_optimizer(evaluate)
    self.assertEqual(result.pareto_frontier, ())
    self.assertTrue(all(reason == "HARD_CONSTRAINT" for reason in result.excluded.values()))

  def test_hard_maximum_objective_is_minimized_on_pareto_frontier(self):
    values = {"a": {"gain": 1.0, "worst": -0.5}, "b": {"gain": 1.0, "worst": 0.0}, "c": {"gain": 0.0, "worst": 0.0}}
    def evaluate(candidate):
      return CandidateEvaluation(candidate.candidate_id, values[candidate.candidate_id], True, True)
    result = self.run_optimizer(evaluate)
    self.assertEqual(result.pareto_frontier, ("a",))

  def test_budget_and_tie_order_are_deterministic(self):
    def evaluate(candidate):
      return CandidateEvaluation(candidate.candidate_id, {"gain": 1.0, "worst": 0.0}, True, True)
    result = self.run_optimizer(evaluate, budget=2)
    self.assertEqual(result.evaluated_ids, ("a", "b"))
    self.assertEqual(result.pareto_frontier, ("a", "b"))


if __name__ == "__main__":
  unittest.main()
