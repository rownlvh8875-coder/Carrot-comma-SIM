from __future__ import annotations

"""Deterministic recorded-scenario WorldBackend.

This is the first concrete backend for the versioned simulator contract. It keeps
road/lead context exogenous and deterministic while the ego response remains the
responsibility of a separate VehiclePlant. It is intentionally not an interactive
traffic simulator and is not acceptance evidence by itself.
"""

from dataclasses import dataclass
import bisect

from .simulator_contract import VehicleState, WorldBackend, WorldObservation


@dataclass(frozen=True)
class RecordedWorldFrame:
  time_s: float
  road_curvature_1pm: float | None = None
  roll_rad: float | None = None
  lead_present: bool = False
  lead_distance_m: float | None = None
  lead_relative_speed_mps: float | None = None
  lead_accel_mps2: float | None = None

  def observation(self) -> WorldObservation:
    return WorldObservation(
      road_curvature_1pm=self.road_curvature_1pm,
      roll_rad=self.roll_rad,
      lead_present=self.lead_present,
      lead_distance_m=self.lead_distance_m,
      lead_relative_speed_mps=self.lead_relative_speed_mps,
      lead_accel_mps2=self.lead_accel_mps2,
      metadata={
        "source": "recorded_scenario",
        "time_s": float(self.time_s),
        "ego_coupling_mode": "exogenous_recorded_world",
        "interactive_traffic": False,
      },
    )


class RecordedScenarioWorld(WorldBackend):
  """Piecewise-constant deterministic world observations from recorded frames.

  The backend deliberately does not modify the ego state. A separate VehiclePlant
  must update ego speed/acceleration/lateral state. Lead and road context remain
  exogenous, matching the current counterfactual-world assumption used by the
  existing longitudinal screening model.
  """

  def __init__(self, frames: list[RecordedWorldFrame], backend_id: str = "recorded-scenario-v1") -> None:
    if not frames:
      raise ValueError("RecordedScenarioWorld requires at least one frame")
    ordered = sorted(frames, key=lambda f: float(f.time_s))
    times = [float(f.time_s) for f in ordered]
    if any(b <= a for a, b in zip(times, times[1:])):
      raise ValueError("recorded world frame times must be strictly increasing")
    self._frames = ordered
    self._times = times
    self._backend_id = str(backend_id)
    self._time_s = times[0]

  @property
  def backend_id(self) -> str:
    return self._backend_id

  @property
  def interactive_traffic(self) -> bool:
    return False

  def _frame_at(self, time_s: float) -> RecordedWorldFrame:
    index = bisect.bisect_right(self._times, float(time_s)) - 1
    index = max(0, min(index, len(self._frames) - 1))
    return self._frames[index]

  def reset(self, ego_state: VehicleState) -> WorldObservation:
    self._time_s = self._times[0]
    obs = self._frame_at(self._time_s).observation()
    return WorldObservation(
      **{k: v for k, v in obs.__dict__.items() if k != "metadata"},
      metadata={
        **obs.metadata,
        "backend_id": self.backend_id,
        "reset_ego_time_s": ego_state.time_s,
      },
    )

  def advance(self, ego_state: VehicleState, dt_s: float) -> WorldObservation:
    dt = float(dt_s)
    if dt <= 0.0:
      raise ValueError("dt_s must be > 0")
    self._time_s += dt
    obs = self._frame_at(self._time_s).observation()
    return WorldObservation(
      **{k: v for k, v in obs.__dict__.items() if k != "metadata"},
      metadata={
        **obs.metadata,
        "backend_id": self.backend_id,
        "simulation_time_s": self._time_s,
        "ego_state_consumed_for_world_interaction": False,
        "ego_time_s": ego_state.time_s,
      },
    )
