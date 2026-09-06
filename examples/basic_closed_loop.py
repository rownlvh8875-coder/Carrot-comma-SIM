from __future__ import annotations

"""Small synthetic closed-loop example.

This example uses toy axis models and a toy controller. It demonstrates the
public simulator API only; it is not Santa Fe validation evidence and it does
not represent Carrot/openpilot control performance.
"""

from pathlib import Path
import sys

# Allow `python examples/basic_closed_loop.py` from a fresh clone.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


class NeutralLateralAxis(LateralAxisPlant):
    @property
    def axis_id(self) -> str:
        return "toy-neutral-lateral"

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


class PassThroughLongitudinalAxis(LongitudinalAxisPlant):
    @property
    def axis_id(self) -> str:
        return "toy-pass-through-longitudinal"

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


class SimpleLeadWorld(WorldBackend):
    def __init__(self) -> None:
        self._distance_m = 45.0
        self._lead_speed_mps = 12.0

    @property
    def backend_id(self) -> str:
        return "toy-simple-lead-world"

    def _observation(self, ego_state: VehicleState) -> WorldObservation:
        return WorldObservation(
            lead_present=True,
            lead_distance_m=max(0.0, self._distance_m),
            lead_relative_speed_mps=self._lead_speed_mps - ego_state.speed_mps,
        )

    def reset(self, ego_state: VehicleState) -> WorldObservation:
        self._distance_m = 45.0
        return self._observation(ego_state)

    def advance(self, ego_state: VehicleState, dt_s: float) -> WorldObservation:
        relative_speed = self._lead_speed_mps - ego_state.speed_mps
        self._distance_m += relative_speed * dt_s
        return self._observation(ego_state)


def toy_controller(state: VehicleState, world: WorldObservation) -> PlantControl:
    target_speed_mps = 13.0
    request = max(-2.0, min(1.5, 0.6 * (target_speed_mps - state.speed_mps)))

    # Add a simple distance response so the example visibly closes the loop.
    if world.lead_present and world.lead_distance_m is not None:
        if world.lead_distance_m < 18.0:
            request = min(request, -1.5)
        elif world.lead_distance_m < 28.0:
            request = min(request, -0.4)

    return PlantControl(
        dt_s=0.1,
        lateral_command=0.0,
        longitudinal_accel_request_mps2=request,
        lateral_source="toy-controller",
        longitudinal_source="toy-controller",
    )


def main() -> None:
    plant = CombinedVehiclePlant(
        metadata=PlantMetadata(
            plant_id="toy-generic-vehicle",
            vehicle="SYNTHETIC_DEMO_VEHICLE",
            model_version="demo-1",
            provenance="synthetic-example-only",
            control_period_s=0.1,
            domain=PlantDomain(
                min_speed_mps=0.0,
                max_speed_mps=40.0,
                max_abs_lateral_command=1.0,
                min_longitudinal_accel_request_mps2=-3.0,
                max_longitudinal_accel_request_mps2=2.0,
            ),
        ),
        lateral=NeutralLateralAxis(),
        longitudinal=PassThroughLongitudinalAxis(),
    )

    trace = run_closed_loop(
        world=SimpleLeadWorld(),
        plant=plant,
        controller=toy_controller,
        initial_state=VehicleState(time_s=0.0, speed_mps=8.0, accel_mps2=0.0),
        duration_s=8.0,
    )

    print("Carrot-comma-SIM synthetic API demo")
    print(f"steps: {len(trace.steps)}")
    print(f"final speed: {trace.final_state.speed_mps:.3f} m/s")
    print(f"distance travelled: {trace.final_state.x_m:.3f} m")
    print(f"out-of-domain steps: {trace.out_of_domain_step_count}")
    print(f"real vehicle write: {trace.real_vehicle_write}")


if __name__ == "__main__":
    main()
