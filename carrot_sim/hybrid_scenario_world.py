from __future__ import annotations

from dataclasses import dataclass
import re

from .simulator_contract import VehicleState, WorldBackend, WorldObservation


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class OverlayPolicy:
  allowed_channels: tuple[str, ...]

  def __post_init__(self) -> None:
    if len(set(self.allowed_channels)) != len(self.allowed_channels):
      raise ValueError("overlay channels must be unique")


@dataclass(frozen=True)
class SyntheticOverlay:
  channel: str
  observation: WorldObservation


@dataclass(frozen=True)
class OverlayReceipt:
  channel: str | None
  before_modelv2_sha256: str
  after_modelv2_sha256: str
  real_vehicle_write: bool = False


class HybridScenarioWorld(WorldBackend):
  def __init__(
    self,
    recorded: WorldBackend,
    overlay: SyntheticOverlay | None,
    policy: OverlayPolicy,
    *,
    recorded_modelv2_sha256: str,
  ) -> None:
    if not _SHA256.fullmatch(recorded_modelv2_sha256):
      raise ValueError("recorded_modelv2_sha256 must be lowercase SHA-256")
    if overlay is not None and overlay.channel not in policy.allowed_channels:
      raise ValueError(f"overlay channel is not allowed: {overlay.channel}")
    self.recorded = recorded
    self.overlay = overlay
    self.policy = policy
    self._model_hash = recorded_modelv2_sha256

  @property
  def backend_id(self) -> str:
    channel = self.overlay.channel if self.overlay else "none"
    return f"hybrid:{self.recorded.backend_id}:{channel}"

  def _combine(self, base: WorldObservation) -> WorldObservation:
    if self.overlay is None:
      return base
    if self.overlay.channel != "radarState":
      raise RuntimeError("validated overlay policy supports radarState only")
    overlay = self.overlay.observation
    return WorldObservation(
      road_curvature_1pm=base.road_curvature_1pm,
      roll_rad=base.roll_rad,
      lead_present=overlay.lead_present,
      lead_distance_m=overlay.lead_distance_m,
      lead_relative_speed_mps=overlay.lead_relative_speed_mps,
      lead_accel_mps2=overlay.lead_accel_mps2,
      traffic_actors=overlay.traffic_actors,
      metadata={
        **base.metadata,
        "overlay_channel": self.overlay.channel,
        "recorded_modelv2_sha256": self._model_hash,
        "modelv2_preserved": True,
        "real_vehicle_write": False,
      },
    )

  def reset(self, ego_state: VehicleState) -> WorldObservation:
    return self._combine(self.recorded.reset(ego_state))

  def advance(self, ego_state: VehicleState, dt_s: float) -> WorldObservation:
    return self._combine(self.recorded.advance(ego_state, dt_s))

  def overlay_receipt(self) -> OverlayReceipt:
    return OverlayReceipt(
      channel=self.overlay.channel if self.overlay else None,
      before_modelv2_sha256=self._model_hash,
      after_modelv2_sha256=self._model_hash,
    )
