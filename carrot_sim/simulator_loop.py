from __future__ import annotations

"""Generic fail-closed closed-loop composition for WorldBackend + VehiclePlant."""

from dataclasses import dataclass
import math
from typing import Callable

from .simulator_contract import (
    DEFAULT_INTEGRATION_POLICY,
    IntegrationPolicy,
    PlantControl,
    VehiclePlant,
    VehicleState,
    WorldBackend,
    WorldObservation,
)

ControllerFn = Callable[[VehicleState, WorldObservation], PlantControl]
TeacherForceFn = Callable[
    [VehicleState, PlantControl, WorldObservation, list[str]],
    VehicleState,
]


@dataclass(frozen=True)
class SimulationStep:
    index: int
    state_before: VehicleState
    world_observation: WorldObservation
    control: PlantControl
    domain_violations: tuple[str, ...]
    state_after: VehicleState
    teacher_forced: bool = False


@dataclass(frozen=True)
class SimulationTrace:
    world_backend_id: str
    plant_id: str
    initial_state: VehicleState
    final_state: VehicleState
    steps: tuple[SimulationStep, ...]
    out_of_domain_step_count: int
    teacher_forced_step_count: int
    synthetic_world_is_acceptance_evidence: bool
    parameter_tuning_authorized: bool
    real_vehicle_write: bool


def _finite_positive(name: str, value: float) -> float:
    out = float(value)
    if not math.isfinite(out) or out <= 0.0:
        raise ValueError(f"{name} must be finite and > 0")
    return out


def run_closed_loop(
    *,
    world: WorldBackend,
    plant: VehiclePlant,
    controller: ControllerFn,
    initial_state: VehicleState,
    duration_s: float,
    policy: IntegrationPolicy = DEFAULT_INTEGRATION_POLICY,
    teacher_force: TeacherForceFn | None = None,
) -> SimulationTrace:
    """Compose a controller, vehicle plant and world backend.

    Out-of-domain behavior is fail-closed. Under the default policy, a domain
    violation raises unless an explicit teacher-force callback is supplied.
    Teacher-forced steps remain explicitly marked in the trace.
    """

    duration = _finite_positive("duration_s", duration_s)
    dt = _finite_positive("plant control_period_s", plant.metadata.control_period_s)

    if policy.external_world_may_replace_calibrated_vehicle_plant:
        raise ValueError(
            "integration policy may not allow the world to replace the vehicle plant"
        )
    if policy.real_vehicle_write or plant.metadata.real_vehicle_write:
        raise ValueError("real_vehicle_write must remain false in simulator loop")

    state = plant.reset(initial_state)
    world_obs = world.reset(state)
    steps: list[SimulationStep] = []
    ood_steps = 0
    teacher_steps = 0

    # Whole fixed periods cover the horizon. Ignore only quotient roundoff
    # within four ULPs of an integer (e.g. (0.1 + 0.2) / 0.1).
    step_ratio = duration / dt
    nearest = round(step_ratio)
    if nearest >= 1 and abs(step_ratio - nearest) <= 4 * math.ulp(step_ratio):
        step_ratio = nearest
    max_steps = max(1, int(math.ceil(step_ratio)))
    for index in range(max_steps):
        control = controller(state, world_obs)
        control_dt = float(control.dt_s)
        if not math.isfinite(control_dt) or control_dt <= 0.0:
            raise ValueError("controller returned invalid dt_s")
        if abs(control_dt - dt) > max(1e-9, dt * 1e-6):
            raise ValueError(
                f"controller dt_s {control_dt} does not match "
                f"plant control_period_s {dt}"
            )

        violations = plant.metadata.domain.violations(state, control)
        teacher_forced = False
        if violations:
            ood_steps += 1
            if teacher_force is None:
                raise RuntimeError(
                    "vehicle plant operating-domain violation: "
                    + ",".join(violations)
                )
            if not plant.supports_state_assimilation:
                raise RuntimeError("teacher force requires history-preserving state assimilation")
            next_state = teacher_force(state, control, world_obs, violations)
            teacher_forced = True
            teacher_steps += 1
        else:
            next_state = plant.step(control, world_obs)

        if next_state.time_s <= state.time_s:
            raise RuntimeError("vehicle plant/teacher force must advance time")
        if abs((next_state.time_s - state.time_s) - dt) > max(1e-6, dt * 1e-3):
            raise RuntimeError("state time step does not match control period")

        if teacher_forced:
            plant.assimilate_state(state, next_state, control, world_obs)

        steps.append(
            SimulationStep(
                index=index,
                state_before=state,
                world_observation=world_obs,
                control=control,
                domain_violations=tuple(violations),
                state_after=next_state,
                teacher_forced=teacher_forced,
            )
        )
        state = next_state
        world_obs = world.advance(state, dt)

    return SimulationTrace(
        world_backend_id=world.backend_id,
        plant_id=plant.metadata.plant_id,
        initial_state=initial_state,
        final_state=state,
        steps=tuple(steps),
        out_of_domain_step_count=ood_steps,
        teacher_forced_step_count=teacher_steps,
        synthetic_world_is_acceptance_evidence=(
            policy.synthetic_world_is_acceptance_evidence
        ),
        parameter_tuning_authorized=policy.parameter_tuning_authorized,
        real_vehicle_write=policy.real_vehicle_write,
    )
