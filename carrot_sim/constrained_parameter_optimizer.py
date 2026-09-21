from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

from .optimization_ledger import OptimizationLedger
from .parameter_search_space import ParameterCandidate


@dataclass(frozen=True)
class CandidateEvaluation:
  candidate_id: str
  objectives: Mapping[str, float]
  safe: bool
  observable: bool


@dataclass(frozen=True)
class OptimizerConfig:
  objective_names: tuple[str, ...]
  hard_maximums: Mapping[str, float]
  budget: int

  def __post_init__(self) -> None:
    if not self.objective_names or self.budget <= 0:
      raise ValueError("optimizer requires objectives and positive budget")
    if any(name not in self.objective_names for name in self.hard_maximums):
      raise ValueError("hard constraint must name an objective")


@dataclass(frozen=True)
class OptimizationResult:
  evaluated_ids: tuple[str, ...]
  excluded: dict[str, str]
  pareto_frontier: tuple[str, ...]
  objective_values: dict[str, dict[str, float]]
  aggregate_winner: None = None


Evaluator = Callable[[ParameterCandidate], CandidateEvaluation]


def _dominates(
  left: Mapping[str, float],
  right: Mapping[str, float],
  names: tuple[str, ...],
  minimize: frozenset[str],
) -> bool:
  comparisons = [
    (float(left[name]) <= float(right[name]), float(left[name]) < float(right[name]))
    if name in minimize else
    (float(left[name]) >= float(right[name]), float(left[name]) > float(right[name]))
    for name in names
  ]
  return all(weak for weak, _strict in comparisons) and any(strict for _weak, strict in comparisons)


def run_search(
  candidates: Iterable[ParameterCandidate],
  ledger: OptimizationLedger,
  evaluator: Evaluator,
  config: OptimizerConfig,
) -> OptimizationResult:
  ordered = tuple(candidates)[:config.budget]
  completed = ledger.completed_records()
  evaluations: dict[str, CandidateEvaluation] = {}
  evaluated_ids: list[str] = []
  for candidate in ordered:
    evaluated_ids.append(candidate.candidate_id)
    if candidate.candidate_id in completed:
      row = completed[candidate.candidate_id]
      evaluations[candidate.candidate_id] = CandidateEvaluation(
        candidate.candidate_id,
        {name: float(value) for name, value in row["objectives"].items()},
        bool(row["safe"]),
        bool(row["observable"]),
      )
      continue
    if not ledger.reserve(candidate.candidate_id):
      continue
    evaluation = evaluator(candidate)
    if evaluation.candidate_id != candidate.candidate_id:
      raise ValueError("evaluator returned a mismatched candidate_id")
    record = {
      "objectives": {name: float(evaluation.objectives[name]) for name in config.objective_names},
      "safe": evaluation.safe,
      "observable": evaluation.observable,
    }
    ledger.complete(candidate.candidate_id, record)
    evaluations[candidate.candidate_id] = evaluation

  excluded: dict[str, str] = {}
  eligible: dict[str, dict[str, float]] = {}
  for candidate_id in evaluated_ids:
    evaluation = evaluations[candidate_id]
    values = {name: float(evaluation.objectives[name]) for name in config.objective_names}
    if not evaluation.safe:
      excluded[candidate_id] = "SAFETY"
    elif not evaluation.observable:
      excluded[candidate_id] = "UNOBSERVABLE"
    elif any(values[name] > limit for name, limit in config.hard_maximums.items()):
      excluded[candidate_id] = "HARD_CONSTRAINT"
    else:
      eligible[candidate_id] = values

  frontier = tuple(sorted(
    candidate_id for candidate_id, values in eligible.items()
    if not any(
      other_id != candidate_id and _dominates(
        other_values, values, config.objective_names, frozenset(config.hard_maximums)
      )
      for other_id, other_values in eligible.items()
    )
  ))
  return OptimizationResult(
    evaluated_ids=tuple(evaluated_ids),
    excluded=excluded,
    pareto_frontier=frontier,
    objective_values=eligible,
  )
