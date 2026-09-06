from __future__ import annotations

"""Composable axis-level vehicle plant interfaces.

`CombinedVehiclePlant` is the reusable multi-vehicle composition primitive.
`CombinedSantaFePlant` remains a strict specialization for the first reference
vehicle, `HYUNDAI_SANTA_FE_2022`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math

from .simulator_contract import (
    PlantControl,
    PlantMetadata,
    VehiclePlant,
    VehicleState,
    WorldObservation,
)


@dataclass(frozen=True)
class LateralAxisResult:
    lateral_accel_mps2: float
    steering_angle_deg: float | None = None
    yaw_rate_rps: float | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("lateral_accel_mps2", self.lateral_accel_mps2),
            ("steering_angle_deg", self.steering_angle_deg),
            ("yaw_rate_rps", self.yaw_rate_rps),
        ):
            if value is not None and not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite when provided")


@dataclass(frozen=True)
class LongitudinalAxisResult:
    accel_mps2: float

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.accel_mps2)):
            raise ValueError("accel_mps2 must be finite")


class LateralAxisPlant(ABC):
    @property
    @abstractmethod
    def axis_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def reset(self, initial_state: VehicleState) -> None:
        raise NotImplementedError

    @abstractmethod
    def step(
        self,
        state: VehicleState,
        command: float | None,
        world: WorldObservation,
        dt_s: float,
    ) -> LateralAxisResult:
        raise NotImplementedError


class LongitudinalAxisPlant(ABC):
    @property
    @abstractmethod
    def axis_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def reset(self, initial_state: VehicleState) -> None:
        raise NotImplementedError

    @abstractmethod
    def step(
        self,
        state: VehicleState,
        accel_request_mps2: float | None,
        world: WorldObservation,
        dt_s: float,
    ) -> LongitudinalAxisResult:
        raise NotImplementedError


class UnavailableLateralAxis(LateralAxisPlant):
    """Fail-closed placeholder until a lateral adapter is explicitly supplied."""

    def __init__(self, reason: str) -> None:
        self.reason = str(reason)

    @property
    def axis_id(self) -> str:
        return "lateral-unavailable"

    def reset(self, initial_state: VehicleState) -> None:
        return None

    def step(
        self,
        state: VehicleState,
        command: float | None,
        world: WorldObservation,
        dt_s: float,
    ) -> LateralAxisResult:
        if command is not None:
            raise RuntimeError(f"lateral axis unavailable: {self.reason}")
        return LateralAxisResult(
            lateral_accel_mps2=state.lateral_accel_mps2,
            steering_angle_deg=state.steering_angle_deg,
            yaw_rate_rps=state.yaw_rate_rps,
        )


class UnavailableLongitudinalAxis(LongitudinalAxisPlant):
    """Fail-closed placeholder until longitudinal evidence is sufficient."""

    def __init__(self, reason: str) -> None:
        self.reason = str(reason)

    @property
    def axis_id(self) -> str:
        return "longitudinal-unavailable"

    def reset(self, initial_state: VehicleState) -> None:
        return None

    def step(
        self,
        state: VehicleState,
        accel_request_mps2: float | None,
        world: WorldObservation,
        dt_s: float,
    ) -> LongitudinalAxisResult:
        if accel_request_mps2 is not None:
            raise RuntimeError(f"longitudinal axis unavailable: {self.reason}")
        return LongitudinalAxisResult(accel_mps2=state.accel_mps2)


class CombinedVehiclePlant(VehiclePlant):
    """Compose independently validated lateral and longitudinal axes."""

    def __init__(
        self,
        *,
        metadata: PlantMetadata,
        lateral: LateralAxisPlant,
        longitudinal: LongitudinalAxisPlant,
    ) -> None:
        self._metadata = metadata
        self.lateral = lateral
        self.longitudinal = longitudinal
        self._state: VehicleState | None = None

    @property
    def metadata(self) -> PlantMetadata:
        return self._metadata

    def reset(self, initial_state: VehicleState) -> VehicleState:
        self._state = initial_state
        self.lateral.reset(initial_state)
        self.longitudinal.reset(initial_state)
        return initial_state

    def step(self, control: PlantControl, world: WorldObservation) -> VehicleState:
        if self._state is None:
            raise RuntimeError("CombinedVehiclePlant must be reset before step")

        dt = float(control.dt_s)
        expected = float(self.metadata.control_period_s)
        if abs(dt - expected) > max(1e-9, expected * 1e-6):
            raise ValueError("control dt does not match combined plant metadata")

        state = self._state
        lat = self.lateral.step(state, control.lateral_command, world, dt)
        lon = self.longitudinal.step(
            state,
            control.longitudinal_accel_request_mps2,
            world,
            dt,
        )

        # Only longitudinal x integration is included in the public core.
        # Lateral pose integration must be supplied as a separately validated layer.
        v_next = max(0.0, state.speed_mps + lon.accel_mps2 * dt)
        x_next = state.x_m + 0.5 * (state.speed_mps + v_next) * dt
        steer_next = (
            lat.steering_angle_deg
            if lat.steering_angle_deg is not None
            else state.steering_angle_deg
        )
        yaw_next = (
            lat.yaw_rate_rps
            if lat.yaw_rate_rps is not None
            else state.yaw_rate_rps
        )

        self._state = VehicleState(
            time_s=state.time_s + dt,
            speed_mps=v_next,
            accel_mps2=lon.accel_mps2,
            lateral_accel_mps2=lat.lateral_accel_mps2,
            steering_angle_deg=steer_next,
            yaw_rate_rps=yaw_next,
            x_m=x_next,
            y_m=state.y_m,
        )
        return self._state


class CombinedSantaFePlant(VehiclePlant):
    """Strict reference wrapper for `HYUNDAI_SANTA_FE_2022`."""

    VEHICLE_ID = "HYUNDAI_SANTA_FE_2022"

    def __init__(
        self,
        *,
        metadata: PlantMetadata,
        lateral: LateralAxisPlant,
        longitudinal: LongitudinalAxisPlant,
    ) -> None:
        if metadata.vehicle != self.VEHICLE_ID:
            raise ValueError(
                f"CombinedSantaFePlant requires {self.VEHICLE_ID} metadata"
            )
        self._combined = CombinedVehiclePlant(
            metadata=metadata,
            lateral=lateral,
            longitudinal=longitudinal,
        )
        self.lateral = lateral
        self.longitudinal = longitudinal

    @property
    def metadata(self) -> PlantMetadata:
        return self._combined.metadata

    def reset(self, initial_state: VehicleState) -> VehicleState:
        return self._combined.reset(initial_state)

    def step(self, control: PlantControl, world: WorldObservation) -> VehicleState:
        return self._combined.step(control, world)
