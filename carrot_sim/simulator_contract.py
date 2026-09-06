from __future__ import annotations

"""Versioned simulator integration contract for the public multi-vehicle core.

The contract separates a vehicle-response plant from the scenario/world backend.
An external world may provide roads, traffic and sensor conditions, but it may
not silently replace a calibrated ego-vehicle plant.

This module is intentionally offline-only: it performs no controller replay,
parameter tuning, Params mutation or real-vehicle writes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import math
from typing import Any


CONTRACT_VERSION = "3-carrot-sim-public-multivehicle-world-plant"


def _finite(name: str, value: float) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _optional_finite(name: str, value: float | None) -> float | None:
    return None if value is None else _finite(name, value)


@dataclass(frozen=True)
class PlantControl:
    """Controller output presented to the vehicle plant for one simulation step."""

    dt_s: float
    lateral_command: float | None = None
    longitudinal_accel_request_mps2: float | None = None
    lateral_source: str = "unspecified"
    longitudinal_source: str = "unspecified"

    def __post_init__(self) -> None:
        dt = _finite("dt_s", self.dt_s)
        if dt <= 0.0:
            raise ValueError("dt_s must be > 0")
        _optional_finite("lateral_command", self.lateral_command)
        _optional_finite(
            "longitudinal_accel_request_mps2",
            self.longitudinal_accel_request_mps2,
        )


@dataclass(frozen=True)
class VehicleState:
    """Minimal ego state shared between controller bridge, plant and world."""

    time_s: float
    speed_mps: float
    accel_mps2: float
    lateral_accel_mps2: float = 0.0
    steering_angle_deg: float | None = None
    yaw_rate_rps: float | None = None
    x_m: float = 0.0
    y_m: float = 0.0

    def __post_init__(self) -> None:
        _finite("time_s", self.time_s)
        speed = _finite("speed_mps", self.speed_mps)
        if speed < 0.0:
            raise ValueError("speed_mps must be >= 0")
        _finite("accel_mps2", self.accel_mps2)
        _finite("lateral_accel_mps2", self.lateral_accel_mps2)
        _optional_finite("steering_angle_deg", self.steering_angle_deg)
        _optional_finite("yaw_rate_rps", self.yaw_rate_rps)
        _finite("x_m", self.x_m)
        _finite("y_m", self.y_m)


@dataclass(frozen=True)
class TrafficActorState:
    """Ego-relative state for one surrounding traffic participant."""

    actor_id: str
    kind: str = "vehicle"
    longitudinal_distance_m: float = 0.0
    lateral_offset_m: float = 0.0
    relative_speed_mps: float = 0.0
    accel_mps2: float | None = None
    length_m: float | None = None
    width_m: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.actor_id).strip():
            raise ValueError("actor_id must be non-empty")
        if not str(self.kind).strip():
            raise ValueError("kind must be non-empty")
        _finite("longitudinal_distance_m", self.longitudinal_distance_m)
        _finite("lateral_offset_m", self.lateral_offset_m)
        _finite("relative_speed_mps", self.relative_speed_mps)
        _optional_finite("accel_mps2", self.accel_mps2)
        length = _optional_finite("length_m", self.length_m)
        width = _optional_finite("width_m", self.width_m)
        if length is not None and length <= 0.0:
            raise ValueError("length_m must be > 0 when provided")
        if width is not None and width <= 0.0:
            raise ValueError("width_m must be > 0 when provided")


@dataclass(frozen=True)
class WorldObservation:
    """Exogenous scenario state supplied by a world backend."""

    road_curvature_1pm: float | None = None
    roll_rad: float | None = None
    lead_present: bool = False
    lead_distance_m: float | None = None
    lead_relative_speed_mps: float | None = None
    lead_accel_mps2: float | None = None
    traffic_actors: tuple[TrafficActorState, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _optional_finite("road_curvature_1pm", self.road_curvature_1pm)
        _optional_finite("roll_rad", self.roll_rad)
        _optional_finite("lead_distance_m", self.lead_distance_m)
        _optional_finite("lead_relative_speed_mps", self.lead_relative_speed_mps)
        _optional_finite("lead_accel_mps2", self.lead_accel_mps2)
        if self.lead_present and self.lead_distance_m is not None:
            if self.lead_distance_m < 0.0:
                raise ValueError("lead_distance_m must be >= 0 when provided")
        actor_ids = [actor.actor_id for actor in self.traffic_actors]
        if len(actor_ids) != len(set(actor_ids)):
            raise ValueError("traffic_actors actor_id values must be unique")


@dataclass(frozen=True)
class PlantDomain:
    """Declared operating envelope for one evidence-bound vehicle plant."""

    min_speed_mps: float | None = None
    max_speed_mps: float | None = None
    max_abs_lateral_command: float | None = None
    min_longitudinal_accel_request_mps2: float | None = None
    max_longitudinal_accel_request_mps2: float | None = None
    max_abs_lateral_accel_mps2: float | None = None

    def __post_init__(self) -> None:
        min_speed = _optional_finite("min_speed_mps", self.min_speed_mps)
        max_speed = _optional_finite("max_speed_mps", self.max_speed_mps)
        max_lat_cmd = _optional_finite(
            "max_abs_lateral_command",
            self.max_abs_lateral_command,
        )
        min_long = _optional_finite(
            "min_longitudinal_accel_request_mps2",
            self.min_longitudinal_accel_request_mps2,
        )
        max_long = _optional_finite(
            "max_longitudinal_accel_request_mps2",
            self.max_longitudinal_accel_request_mps2,
        )
        max_lat_accel = _optional_finite(
            "max_abs_lateral_accel_mps2",
            self.max_abs_lateral_accel_mps2,
        )

        if min_speed is not None and min_speed < 0.0:
            raise ValueError("min_speed_mps must be >= 0")
        if max_speed is not None and max_speed < 0.0:
            raise ValueError("max_speed_mps must be >= 0")
        if min_speed is not None and max_speed is not None and min_speed > max_speed:
            raise ValueError("min_speed_mps must be <= max_speed_mps")
        if max_lat_cmd is not None and max_lat_cmd <= 0.0:
            raise ValueError("max_abs_lateral_command must be > 0")
        if min_long is not None and max_long is not None and min_long > max_long:
            raise ValueError(
                "min_longitudinal_accel_request_mps2 must be <= "
                "max_longitudinal_accel_request_mps2"
            )
        if max_lat_accel is not None and max_lat_accel <= 0.0:
            raise ValueError("max_abs_lateral_accel_mps2 must be > 0")

    def violations(self, state: VehicleState, control: PlantControl) -> list[str]:
        out: list[str] = []
        if self.min_speed_mps is not None and state.speed_mps < self.min_speed_mps:
            out.append("speed_below_validated_domain")
        if self.max_speed_mps is not None and state.speed_mps > self.max_speed_mps:
            out.append("speed_above_validated_domain")
        if control.lateral_command is not None and self.max_abs_lateral_command is not None:
            if abs(control.lateral_command) > self.max_abs_lateral_command:
                out.append("lateral_command_outside_validated_domain")
        if control.longitudinal_accel_request_mps2 is not None:
            request = control.longitudinal_accel_request_mps2
            if (
                self.min_longitudinal_accel_request_mps2 is not None
                and request < self.min_longitudinal_accel_request_mps2
            ):
                out.append("longitudinal_request_below_validated_domain")
            if (
                self.max_longitudinal_accel_request_mps2 is not None
                and request > self.max_longitudinal_accel_request_mps2
            ):
                out.append("longitudinal_request_above_validated_domain")
        if (
            self.max_abs_lateral_accel_mps2 is not None
            and abs(state.lateral_accel_mps2) > self.max_abs_lateral_accel_mps2
        ):
            out.append("lateral_accel_outside_validated_domain")
        return out


@dataclass(frozen=True)
class PlantMetadata:
    plant_id: str
    vehicle: str
    model_version: str
    provenance: str
    control_period_s: float
    domain: PlantDomain
    one_step_fit_is_closed_loop_evidence: bool = False
    real_vehicle_write: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("plant_id", self.plant_id),
            ("vehicle", self.vehicle),
            ("model_version", self.model_version),
            ("provenance", self.provenance),
        ):
            if not str(value).strip():
                raise ValueError(f"{name} must be non-empty")
        period = _finite("control_period_s", self.control_period_s)
        if period <= 0.0:
            raise ValueError("control_period_s must be > 0")
        if self.one_step_fit_is_closed_loop_evidence:
            raise ValueError("one-step fit may not be declared closed-loop evidence")
        if self.real_vehicle_write:
            raise ValueError("VehiclePlant metadata may not authorize real vehicle writes")


class VehiclePlant(ABC):
    """Evidence-bound ego-vehicle response backend."""

    @property
    @abstractmethod
    def metadata(self) -> PlantMetadata:
        raise NotImplementedError

    @abstractmethod
    def reset(self, initial_state: VehicleState) -> VehicleState:
        raise NotImplementedError

    @abstractmethod
    def step(self, control: PlantControl, world: WorldObservation) -> VehicleState:
        raise NotImplementedError


class WorldBackend(ABC):
    """Road/traffic/sensor environment independent of the ego vehicle plant."""

    @property
    @abstractmethod
    def backend_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def reset(self, ego_state: VehicleState) -> WorldObservation:
        raise NotImplementedError

    @abstractmethod
    def advance(self, ego_state: VehicleState, dt_s: float) -> WorldObservation:
        raise NotImplementedError


@dataclass(frozen=True)
class IntegrationPolicy:
    """Fail-closed policy for composing world and plant backends."""

    contract_version: str = CONTRACT_VERSION
    external_world_may_replace_calibrated_vehicle_plant: bool = False
    out_of_domain_behavior: str = "block_or_explicit_teacher_force"
    synthetic_world_is_acceptance_evidence: bool = False
    parameter_tuning_authorized: bool = False
    real_vehicle_write: bool = False

    def __post_init__(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError(
                f"unsupported simulator contract version: {self.contract_version}"
            )
        if self.external_world_may_replace_calibrated_vehicle_plant:
            raise ValueError(
                "external world may not replace a calibrated vehicle plant"
            )
        if self.out_of_domain_behavior != "block_or_explicit_teacher_force":
            raise ValueError(
                f"unsupported out_of_domain_behavior: {self.out_of_domain_behavior}"
            )
        if self.synthetic_world_is_acceptance_evidence:
            raise ValueError("synthetic world may not be acceptance evidence")
        if self.parameter_tuning_authorized:
            raise ValueError("simulator integration policy may not authorize tuning")
        if self.real_vehicle_write:
            raise ValueError("simulator integration policy may not authorize vehicle writes")


DEFAULT_INTEGRATION_POLICY = IntegrationPolicy()
