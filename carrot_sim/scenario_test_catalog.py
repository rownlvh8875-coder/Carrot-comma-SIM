from __future__ import annotations

"""Deterministic scenario test-case catalog and budget prioritization.

The structure is inspired by public scenario/test-case concepts used in AV
validation literature. It does not claim standards compliance and does not
create real-road safety or tuning authority.
"""

from dataclasses import dataclass
import math
from typing import Iterable


def _unit(name: str, value: float) -> float:
    v = float(value)
    if not math.isfinite(v) or not 0.0 <= v <= 1.0:
        raise ValueError(f"{name} must be finite in [0,1]")
    return v


@dataclass(frozen=True)
class ScenarioPriorityFactors:
    exposure: float
    criticality: float
    complexity: float
    coverage_gap: float

    def __post_init__(self) -> None:
        _unit("exposure", self.exposure)
        _unit("criticality", self.criticality)
        _unit("complexity", self.complexity)
        _unit("coverage_gap", self.coverage_gap)


@dataclass(frozen=True)
class ScenarioPriorityPolicy:
    exposure_weight: float = 0.20
    criticality_weight: float = 0.40
    complexity_weight: float = 0.10
    coverage_gap_weight: float = 0.30
    novelty_bonus_weight: float = 0.15

    def __post_init__(self) -> None:
        weights = (
            self.exposure_weight,
            self.criticality_weight,
            self.complexity_weight,
            self.coverage_gap_weight,
            self.novelty_bonus_weight,
        )
        if any(not math.isfinite(float(v)) or float(v) < 0.0 for v in weights):
            raise ValueError("priority weights must be finite and >= 0")
        if sum(weights[:4]) <= 0.0:
            raise ValueError("at least one base priority weight must be > 0")

    def base_score(self, factors: ScenarioPriorityFactors) -> float:
        denom = (
            self.exposure_weight
            + self.criticality_weight
            + self.complexity_weight
            + self.coverage_gap_weight
        )
        return (
            self.exposure_weight * factors.exposure
            + self.criticality_weight * factors.criticality
            + self.complexity_weight * factors.complexity
            + self.coverage_gap_weight * factors.coverage_gap
        ) / denom


@dataclass(frozen=True)
class ScenarioTestCase:
    case_id: str
    scenario_id: str
    objective: str
    inputs: tuple[str, ...]
    steps: tuple[str, ...]
    platform: str
    expected_results: tuple[str, ...]
    coverage_tags: tuple[str, ...]
    priority: ScenarioPriorityFactors
    evidence_role: str = "synthetic_stress"
    real_route_acceptance_eligible: bool = False
    parameter_tuning_authorized: bool = False
    real_vehicle_write: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("case_id", self.case_id),
            ("scenario_id", self.scenario_id),
            ("objective", self.objective),
            ("platform", self.platform),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
        if not self.inputs or not all(x.strip() for x in self.inputs):
            raise ValueError("test-case inputs are required")
        if not self.steps or not all(x.strip() for x in self.steps):
            raise ValueError("test-case steps are required")
        if not self.expected_results or not all(x.strip() for x in self.expected_results):
            raise ValueError("expected_results are required")
        if len(set(self.coverage_tags)) != len(self.coverage_tags):
            raise ValueError("coverage_tags must be unique")
        if self.evidence_role not in {"synthetic_stress", "diagnostic"}:
            raise ValueError("scenario catalog is restricted to synthetic/diagnostic evidence")
        if self.real_route_acceptance_eligible:
            raise ValueError("scenario catalog may not create real-route acceptance evidence")
        if self.parameter_tuning_authorized:
            raise ValueError("scenario catalog may not authorize parameter tuning")
        if self.real_vehicle_write:
            raise ValueError("scenario catalog may not authorize real vehicle writes")


@dataclass(frozen=True)
class PrioritizedScenario:
    test_case: ScenarioTestCase
    base_score: float
    novelty_fraction: float
    selection_score: float


def prioritize_test_cases(
    cases: Iterable[ScenarioTestCase],
    *,
    budget: int,
    policy: ScenarioPriorityPolicy = ScenarioPriorityPolicy(),
) -> tuple[PrioritizedScenario, ...]:
    """Greedy deterministic selection that rewards new coverage."""

    rows = list(cases)
    if budget <= 0:
        raise ValueError("budget must be > 0")
    if len({row.case_id for row in rows}) != len(rows):
        raise ValueError("case_id values must be unique")

    budget = min(budget, len(rows))
    selected: list[PrioritizedScenario] = []
    covered: set[str] = set()
    remaining = {
        row.case_id: (row, policy.base_score(row.priority), frozenset(row.coverage_tags))
        for row in rows
    }
    # Preserve stable-sort behavior for overflowed weights producing NaN scores.
    nonfinite_base = any(not math.isfinite(base) for _, base, _ in remaining.values())

    def candidates():
        for case, base, tags in remaining.values():
            novelty = (len(tags - covered) / len(tags)) if tags else 0.0
            score = base + policy.novelty_bonus_weight * novelty
            yield score, base, novelty, case.case_id, case

    def rank_key(row):
        return -row[0], -row[1], -row[2], row[3]

    while remaining and len(selected) < budget:
        # High score/base/novelty first; lexical case_id breaks ties.
        best = sorted(candidates(), key=rank_key)[0] if nonfinite_base else min(candidates(), key=rank_key)
        score, base, novelty, _, case = best
        selected.append(PrioritizedScenario(case, base, novelty, score))
        covered.update(case.coverage_tags)
        del remaining[case.case_id]

    return tuple(selected)
