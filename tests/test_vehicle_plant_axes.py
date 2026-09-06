from __future__ import annotations

import unittest

from carrot_sim.simulator_contract import (
    PlantControl,
    PlantDomain,
    PlantMetadata,
    VehicleState,
    WorldObservation,
)
from carrot_sim.vehicle_plant_axes import (
    CombinedSantaFePlant,
    CombinedVehiclePlant,
    LateralAxisPlant,
    LateralAxisResult,
    LongitudinalAxisPlant,
    LongitudinalAxisResult,
    UnavailableLongitudinalAxis,
)


class ConstantLateralAxis(LateralAxisPlant):
    @property
    def axis_id(self) -> str:
        return "constant-lateral"

    def reset(self, initial_state: VehicleState) -> None:
        return None

    def step(
        self,
        state: VehicleState,
        command: float | None,
        world: WorldObservation,
        dt_s: float,
    ) -> LateralAxisResult:
        return LateralAxisResult(lateral_accel_mps2=float(command or 0.0))


class ConstantLongitudinalAxis(LongitudinalAxisPlant):
    @property
    def axis_id(self) -> str:
        return "constant-longitudinal"

    def reset(self, initial_state: VehicleState) -> None:
        return None

    def step(
        self,
        state: VehicleState,
        accel_request_mps2: float | None,
        world: WorldObservation,
        dt_s: float,
    ) -> LongitudinalAxisResult:
        return LongitudinalAxisResult(accel_mps2=float(accel_request_mps2 or 0.0))


class VehiclePlantAxesTests(unittest.TestCase):
    def metadata(self, vehicle: str = "HYUNDAI_SANTA_FE_2022") -> PlantMetadata:
        return PlantMetadata(
            plant_id="combined-test",
            vehicle=vehicle,
            model_version="test",
            provenance="unit-test",
            control_period_s=0.1,
            domain=PlantDomain(
                min_speed_mps=0.0,
                max_speed_mps=50.0,
                max_abs_lateral_command=1.0,
                min_longitudinal_accel_request_mps2=-3.0,
                max_longitudinal_accel_request_mps2=2.0,
            ),
        )

    def test_generic_combined_vehicle_plant_accepts_other_vehicle(self) -> None:
        plant = CombinedVehiclePlant(
            metadata=self.metadata("DEMO_OTHER_VEHICLE"),
            lateral=ConstantLateralAxis(),
            longitudinal=ConstantLongitudinalAxis(),
        )
        plant.reset(VehicleState(time_s=0.0, speed_mps=10.0, accel_mps2=0.0))
        out = plant.step(
            PlantControl(
                dt_s=0.1,
                lateral_command=0.4,
                longitudinal_accel_request_mps2=1.0,
            ),
            WorldObservation(),
        )
        self.assertAlmostEqual(out.time_s, 0.1)
        self.assertAlmostEqual(out.speed_mps, 10.1)
        self.assertAlmostEqual(out.accel_mps2, 1.0)
        self.assertAlmostEqual(out.lateral_accel_mps2, 0.4)

    def test_santafe_wrapper_rejects_wrong_vehicle_identity(self) -> None:
        with self.assertRaises(ValueError):
            CombinedSantaFePlant(
                metadata=self.metadata("DEMO_OTHER_VEHICLE"),
                lateral=ConstantLateralAxis(),
                longitudinal=ConstantLongitudinalAxis(),
            )

    def test_unavailable_longitudinal_axis_fails_closed(self) -> None:
        plant = CombinedVehiclePlant(
            metadata=self.metadata(),
            lateral=ConstantLateralAxis(),
            longitudinal=UnavailableLongitudinalAxis("not validated"),
        )
        plant.reset(VehicleState(time_s=0.0, speed_mps=10.0, accel_mps2=0.0))
        with self.assertRaises(RuntimeError):
            plant.step(
                PlantControl(
                    dt_s=0.1,
                    lateral_command=0.0,
                    longitudinal_accel_request_mps2=0.5,
                ),
                WorldObservation(),
            )


if __name__ == "__main__":
    unittest.main()
