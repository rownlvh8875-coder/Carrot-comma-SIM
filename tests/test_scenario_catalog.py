from __future__ import annotations

import unittest

from carrot_sim.scenario_test_catalog import (
    ScenarioPriorityFactors,
    ScenarioTestCase,
    prioritize_test_cases,
)


class ScenarioCatalogTests(unittest.TestCase):
    def case(self, case_id: str, tags: tuple[str, ...], criticality: float) -> ScenarioTestCase:
        return ScenarioTestCase(
            case_id=case_id,
            scenario_id=f"scenario-{case_id}",
            objective="synthetic regression coverage",
            inputs=("ego_speed", "lead_distance"),
            steps=("initialize", "run", "evaluate"),
            platform="offline-simulator",
            expected_results=("trace completes",),
            coverage_tags=tags,
            priority=ScenarioPriorityFactors(
                exposure=0.5,
                criticality=criticality,
                complexity=0.4,
                coverage_gap=0.7,
            ),
        )

    def test_prioritization_is_deterministic(self) -> None:
        cases = (
            self.case("a", ("lead", "brake"), 0.6),
            self.case("b", ("lead", "cut-in"), 0.9),
            self.case("c", ("standstill",), 0.5),
        )
        first = prioritize_test_cases(cases, budget=2)
        second = prioritize_test_cases(cases, budget=2)
        self.assertEqual(
            [x.test_case.case_id for x in first],
            [x.test_case.case_id for x in second],
        )

    def test_scenario_cannot_create_real_vehicle_authority(self) -> None:
        with self.assertRaises(ValueError):
            ScenarioTestCase(
                case_id="unsafe",
                scenario_id="unsafe",
                objective="should fail",
                inputs=("x",),
                steps=("x",),
                platform="offline",
                expected_results=("x",),
                coverage_tags=(),
                priority=ScenarioPriorityFactors(0.5, 0.5, 0.5, 0.5),
                real_vehicle_write=True,
            )


if __name__ == "__main__":
    unittest.main()
