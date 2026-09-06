from __future__ import annotations

import unittest

from carrot_sim.simulator_contract import (
    PlantControl,
    PlantDomain,
    PlantMetadata,
    VehicleState,
    WorldBackend,
    WorldObservation,
)
from carrot_sim.simulator_loop import run_closed_loop
from carrot_sim.vehicle_plant_axes import (
    CombinedVehiclePlant,
    LateralAxisPlant,
    LateralAxisResult,
    LongitudinalAxisPlant,
    LongitudinalAxisResult,
)


class ZeroLateral(LateralAxisPlant):
    @property
    def axis_id(self) -> str:
        return "zero-lateral"

    def reset(self, initial_state: VehicleState) -> None:
        return None

    def step(self, state, command, world, dt_s):
        return LateralAxisResult(lateral_accel_mps2=0.0)


class PassThroughLongitudinal(LongitudinalAxisPlant):
    @property
    def axis_id(self) -> str:
        return "pass-through-longitudinal"

    def reset(self, initial_state: VehicleState) -> None:
        return None

    def step(self, state, accel_request_mps2, world, dt_s):
        return LongitudinalAxisResult(accel_mps2=float(accel_request_mps2 or 0.0))


class EmptyWorld(WorldBackend):
    @property
    def backend_id(self) -> str:
        return "empty-world"

    def reset(self, ego_state: VehicleState) -> WorldObservation:
        return WorldObservation()

    def advance(self, ego_state: VehicleState, dt_s: float) -> WorldObservation:
        return WorldObservation()


class SimulatorLoopTests(unittest.TestCase):
    def plant(self, max_accel: float = 2.0) -> CombinedVehiclePlant:
        return CombinedVehiclePlant(
            metadata=PlantMetadata(
                plant_id="test-plant",
                vehicle="SYNTHETIC_TEST_VEHICLE",
                model_version="test",
                provenance="unit-test",
                control_period_s=0.1,
                domain=PlantDomain(
                    min_speed_mps=0.0,
                    max_speed_mps=40.0,
                    min_longitudinal_accel_request_mps2=-3.0,
                    max_longitudinal_accel_request_mps2=max_accel,
                ),
            ),
            lateral=ZeroLateral(),
            longitudinal=PassThroughLongitudinal(),
        )

    def test_closed_loop_advances_and_never_writes_real_vehicle(self) -> None:
        def controller(state, world):
            return PlantControl(
                dt_s=0.1,
                longitudinal_accel_request_mps2=1.0,
            )

        trace = run_closed_loop(
            world=EmptyWorld(),
            plant=self.plant(),
            controller=controller,
            initial_state=VehicleState(time_s=0.0, speed_mps=5.0, accel_mps2=0.0),
            duration_s=1.0,
        )
        self.assertEqual(len(trace.steps), 10)
        self.assertAlmostEqual(trace.final_state.time_s, 1.0)
        self.assertGreater(trace.final_state.speed_mps, 5.0)
        self.assertFalse(trace.real_vehicle_write)
        self.assertFalse(trace.parameter_tuning_authorized)

    def test_out_of_domain_request_fails_closed(self) -> None:
        def controller(state, world):
            return PlantControl(
                dt_s=0.1,
                longitudinal_accel_request_mps2=1.5,
            )

        with self.assertRaises(RuntimeError):
            run_closed_loop(
                world=EmptyWorld(),
                plant=self.plant(max_accel=1.0),
                controller=controller,
                initial_state=VehicleState(time_s=0.0, speed_mps=5.0, accel_mps2=0.0),
                duration_s=0.2,
            )

    def test_controller_clock_mismatch_fails(self) -> None:
        def controller(state, world):
            return PlantControl(
                dt_s=0.2,
                longitudinal_accel_request_mps2=0.0,
            )

        with self.assertRaises(ValueError):
            run_closed_loop(
                world=EmptyWorld(),
                plant=self.plant(),
                controller=controller,
                initial_state=VehicleState(time_s=0.0, speed_mps=5.0, accel_mps2=0.0),
                duration_s=0.2,
            )


if __name__ == "__main__":
    unittest.main()
