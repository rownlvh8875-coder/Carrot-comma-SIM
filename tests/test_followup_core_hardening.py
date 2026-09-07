from __future__ import annotations

from dataclasses import asdict, replace
import json
import unittest

from carrot_sim.simulator_contract import (
    PlantControl, PlantDomain, PlantMetadata, TrafficActorState, VehicleState,
    WorldBackend, WorldObservation,
)
from carrot_sim.simulator_loop import run_closed_loop
from carrot_sim.vehicle_plant_axes import (
    CombinedVehiclePlant, LateralAxisPlant, LateralAxisResult,
    LongitudinalAxisPlant, LongitudinalAxisResult,
)


class SnapshotWorld(WorldBackend):
    backend_id = "synthetic-snapshot-test"

    def reset(self, ego_state):
        self.shared = {"tick": [0]}
        return WorldObservation(metadata=self.shared)

    def advance(self, ego_state, dt_s):
        self.shared["tick"][0] += 1
        return WorldObservation(metadata=self.shared)


class TestLateral(LateralAxisPlant):
    axis_id = "synthetic-lateral"
    supports_state_assimilation = True

    def reset(self, initial_state):
        self.resets = getattr(self, "resets", 0) + 1
        self.history = []

    def step(self, state, command, world, dt_s):
        self.history.append(("step", state.time_s))
        return LateralAxisResult(lateral_accel_mps2=0.0)

    def assimilate_state(self, state_before, state_after, control, world):
        self.history.append(("forced", state_before.time_s))


class TestLongitudinal(LongitudinalAxisPlant):
    axis_id = "synthetic-longitudinal"
    supports_state_assimilation = True

    def reset(self, initial_state):
        self.resets = getattr(self, "resets", 0) + 1
        self.history = []

    def step(self, state, accel_request_mps2, world, dt_s):
        self.history.append(("step", state.time_s))
        return LongitudinalAxisResult(accel_mps2=accel_request_mps2 or 0.0)

    def assimilate_state(self, state_before, state_after, control, world):
        self.history.append(("forced", state_before.time_s))


def synthetic_plant():
    return CombinedVehiclePlant(
        metadata=PlantMetadata(plant_id="synthetic-test-only", vehicle="TEST_VEHICLE",
            model_version="fixture", provenance="synthetic-unit-test", control_period_s=0.1,
            domain=PlantDomain(min_longitudinal_accel_request_mps2=-2.0,
                max_longitudinal_accel_request_mps2=2.0)),
        lateral=TestLateral(), longitudinal=TestLongitudinal(),
    )


class ObservationSnapshotTests(unittest.TestCase):
    def test_nested_provider_and_actor_aliases_cannot_rewrite_observation(self):
        shared = {"ticks": [0], "nested": {"phase": "before"}}
        actors = [TrafficActorState(actor_id="lead", metadata=shared)]
        obs = WorldObservation(metadata=shared, traffic_actors=actors)
        shared["ticks"][0] = 2
        shared["nested"]["phase"] = "after"
        actors.clear()
        self.assertEqual(obs.metadata["ticks"], [0])
        self.assertEqual(obs.traffic_actors[0].metadata["nested"]["phase"], "before")
        with self.assertRaises(TypeError):
            obs.metadata["ticks"].append(3)
        with self.assertRaises(TypeError):
            obs.metadata["nested"]["phase"] = "mutated"
        with self.assertRaises(TypeError):
            obs.traffic_actors[0].metadata.update({"extra": True})
        exported = json.loads(json.dumps(asdict(obs)))
        self.assertEqual(exported["metadata"]["ticks"], [0])
        self.assertEqual(exported["traffic_actors"][0]["actor_id"], "lead")

    def test_metadata_rejects_mutable_provider_objects(self):
        with self.assertRaises(TypeError):
            WorldObservation(metadata={"provider": object()})

    def test_completed_trace_keeps_each_observation_tick(self):
        trace = run_closed_loop(world=SnapshotWorld(), plant=synthetic_plant(),
            controller=lambda state, obs: PlantControl(dt_s=0.1),
            initial_state=VehicleState(time_s=0.0, speed_mps=10.0, accel_mps2=0.0),
            duration_s=0.2)
        self.assertEqual([step.world_observation.metadata["tick"][0] for step in trace.steps], [0, 1])
        self.assertEqual(len(json.loads(json.dumps(asdict(trace)))["steps"]), 2)


class IntegrationBoundaryTests(unittest.TestCase):
    def test_stop_crossing_and_non_crossing_distances(self):
        for speed, acceleration, expected_speed, expected_distance in (
            (0.1, -2.0, 0.0, 0.0025), (0.2, -2.0, 0.0, 0.01),
            (0.0, -2.0, 0.0, 0.0), (1.0, -2.0, 0.8, 0.09),
            (0.0, 2.0, 0.2, 0.01), (1.0, 0.0, 1.0, 0.1),
        ):
            with self.subTest(speed=speed, acceleration=acceleration):
                plant = synthetic_plant()
                plant.reset(VehicleState(time_s=0.0, speed_mps=speed, accel_mps2=0.0))
                after = plant.step(PlantControl(dt_s=0.1, longitudinal_accel_request_mps2=acceleration), WorldObservation())
                self.assertAlmostEqual(after.speed_mps, expected_speed)
                self.assertAlmostEqual(after.x_m, expected_distance)
                self.assertEqual(after.accel_mps2, acceleration)

    def test_duration_roundoff_preserves_whole_period_coverage(self):
        for duration, count in ((0.3, 3), (0.1 + 0.2, 3), (0.300000001, 4), (0.25, 3)):
            with self.subTest(duration=duration):
                trace = run_closed_loop(world=SnapshotWorld(), plant=synthetic_plant(),
                    controller=lambda state, obs: PlantControl(dt_s=0.1),
                    initial_state=VehicleState(time_s=0.0, speed_mps=1.0, accel_mps2=0.0),
                    duration_s=duration)
                self.assertEqual(len(trace.steps), count)
                self.assertAlmostEqual(trace.final_state.time_s, 0.1 * count)

    def test_forced_interval_preserves_history_and_reenters_normal_plant(self):
        plant = synthetic_plant()
        trace = run_closed_loop(world=SnapshotWorld(), plant=plant,
            controller=lambda state, obs: PlantControl(dt_s=0.1,
                longitudinal_accel_request_mps2=3.0 if 0.05 < state.time_s < 0.15 else 0.5),
            teacher_force=lambda state, control, obs, reasons: replace(state, time_s=state.time_s + 0.1),
            initial_state=VehicleState(time_s=0.0, speed_mps=1.0, accel_mps2=0.0), duration_s=0.3)
        self.assertEqual([step.teacher_forced for step in trace.steps], [False, True, False])
        self.assertAlmostEqual(trace.final_state.time_s, 0.3)
        for axis in (plant.lateral, plant.longitudinal):
            self.assertEqual(axis.resets, 1)
            self.assertEqual(axis.history, [("step", 0.0), ("forced", 0.1), ("step", 0.2)])
        self.assertEqual(trace.teacher_forced_step_count, 1)
        self.assertFalse(trace.synthetic_world_is_acceptance_evidence)
        self.assertFalse(trace.parameter_tuning_authorized)

    def test_unsupported_axis_rejects_before_forced_callback(self):
        plant = synthetic_plant()
        plant.longitudinal.supports_state_assimilation = False
        calls = []
        with self.assertRaisesRegex(RuntimeError, "history-preserving"):
            run_closed_loop(world=SnapshotWorld(), plant=plant,
                controller=lambda state, obs: PlantControl(dt_s=0.1, longitudinal_accel_request_mps2=3.0),
                teacher_force=lambda *args: calls.append(True),
                initial_state=VehicleState(time_s=0.0, speed_mps=1.0, accel_mps2=0.0), duration_s=0.2)
        self.assertEqual(calls, [])
        self.assertEqual(plant.lateral.history, [])

    def test_failed_assimilation_invalidates_partially_consumed_plant(self):
        plant = synthetic_plant()
        before = VehicleState(time_s=0.0, speed_mps=1.0, accel_mps2=0.0)
        plant.reset(before)
        def fail(*args):
            raise RuntimeError("synthetic-axis-assimilation-failure")
        plant.longitudinal.assimilate_state = fail
        with self.assertRaisesRegex(RuntimeError, "synthetic-axis-assimilation-failure"):
            plant.assimilate_state(before, replace(before, time_s=0.1), PlantControl(0.1), WorldObservation())
        with self.assertRaisesRegex(RuntimeError, "must be reset"):
            plant.step(PlantControl(0.1), WorldObservation())

    def test_partial_axis_failure_requires_reset_before_next_step(self):
        plant = synthetic_plant()
        plant.reset(VehicleState(time_s=0.0, speed_mps=1.0, accel_mps2=0.0))
        def fail(*args):
            raise RuntimeError("synthetic-step-failure")
        plant.longitudinal.step = fail
        with self.assertRaisesRegex(RuntimeError, "synthetic-step-failure"):
            plant.step(PlantControl(0.1), WorldObservation())
        self.assertEqual(plant.lateral.history, [("step", 0.0)])
        with self.assertRaisesRegex(RuntimeError, "must be reset"):
            plant.step(PlantControl(0.1), WorldObservation())
        self.assertEqual(plant.lateral.history, [("step", 0.0)])

    def test_invalid_next_state_requires_reset_after_axis_advancement(self):
        plant = synthetic_plant()
        plant.reset(VehicleState(time_s=0.0, speed_mps=1e308, accel_mps2=0.0, x_m=1.79e308))
        with self.assertRaisesRegex(ValueError, "finite"):
            plant.step(PlantControl(0.1), WorldObservation())
        with self.assertRaisesRegex(RuntimeError, "must be reset"):
            plant.step(PlantControl(0.1), WorldObservation())

    def test_failed_reset_does_not_mark_plant_ready(self):
        plant = synthetic_plant()
        def fail(*args):
            raise RuntimeError("synthetic-reset-failure")
        plant.longitudinal.reset = fail
        with self.assertRaisesRegex(RuntimeError, "synthetic-reset-failure"):
            plant.reset(VehicleState(time_s=0.0, speed_mps=1.0, accel_mps2=0.0))
        with self.assertRaisesRegex(RuntimeError, "must be reset"):
            plant.step(PlantControl(0.1), WorldObservation())


if __name__ == "__main__":
    unittest.main()
