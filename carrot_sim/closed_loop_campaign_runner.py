from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Mapping

from .campaign_manifest import content_sha256


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class CampaignRunSpec:
  manifest_hash: str
  scenario_hash: str
  params_hash: str
  controller_hash: str
  plant_hash: str
  dt_s: float

  def __post_init__(self) -> None:
    for name in ("manifest_hash", "scenario_hash", "params_hash", "controller_hash", "plant_hash"):
      if not _SHA256.fullmatch(getattr(self, name)):
        raise ValueError(f"{name} must be lowercase SHA-256")
    if not math.isfinite(self.dt_s) or self.dt_s <= 0.0:
      raise ValueError("dt_s must be finite and positive")


@dataclass(frozen=True)
class SimulationFrame:
  time_s: float
  speed_mps: float = 0.0
  accel_mps2: float = 0.0
  jerk_mps3: float = 0.0
  min_ttc_s: float | None = None
  following_distance_m: float | None = None
  steering_command: float = 0.0
  lateral_error_m: float = 0.0
  yaw_error_rad: float = 0.0
  collision: bool = False
  read_parameters: tuple[str, ...] = ()

  def __post_init__(self) -> None:
    for name in ("time_s", "speed_mps", "accel_mps2", "jerk_mps3", "steering_command", "lateral_error_m", "yaw_error_rad"):
      if not math.isfinite(float(getattr(self, name))):
        raise ValueError(f"{name} must be finite")
    for name in ("min_ttc_s", "following_distance_m"):
      value = getattr(self, name)
      if value is not None and not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite when present")


@dataclass(frozen=True)
class ParameterCoverage:
  read: bool
  trace_effect: bool
  observable: bool


@dataclass(frozen=True)
class ComparisonRun:
  spec: CampaignRunSpec
  baseline_frames: tuple[SimulationFrame, ...]
  candidate_frames: tuple[SimulationFrame, ...]
  parameter_coverage: dict[str, ParameterCoverage]
  credited_changes: tuple[str, ...]
  cache_key: str
  real_vehicle_write: bool = False


def validate_time_grid(frames: tuple[SimulationFrame, ...], dt_s: float) -> None:
  if not frames:
    raise ValueError("simulation frames are required")
  times = [float(frame.time_s) for frame in frames]
  if any(right <= left for left, right in zip(times, times[1:])):
    raise ValueError("frame times must be strictly increasing")
  tolerance = max(1e-9, abs(dt_s) * 1e-6)
  if any(abs((right - left) - dt_s) > tolerance for left, right in zip(times, times[1:])):
    raise ValueError("frame times do not match the configured grid")


def comparison_cache_key(spec: CampaignRunSpec) -> str:
  return content_sha256({
    "manifest_hash": spec.manifest_hash,
    "scenario_hash": spec.scenario_hash,
    "params_hash": spec.params_hash,
    "controller_hash": spec.controller_hash,
    "plant_hash": spec.plant_hash,
    "dt_s": spec.dt_s,
  })


def _trace_differs(
  baseline: tuple[SimulationFrame, ...],
  candidate: tuple[SimulationFrame, ...],
) -> bool:
  fields = ("speed_mps", "accel_mps2", "steering_command", "lateral_error_m", "yaw_error_rad")
  return any(
    any(abs(float(getattr(left, name)) - float(getattr(right, name))) > 1e-12 for name in fields)
    for left, right in zip(baseline, candidate, strict=True)
  )


def run_comparison(
  spec: CampaignRunSpec,
  baseline_frames: tuple[SimulationFrame, ...],
  candidate_frames: tuple[SimulationFrame, ...],
  baseline_params: Mapping[str, object],
  candidate_params: Mapping[str, object],
) -> ComparisonRun:
  baseline_times = tuple(frame.time_s for frame in baseline_frames)
  candidate_times = tuple(frame.time_s for frame in candidate_frames)
  if baseline_times != candidate_times:
    raise ValueError("baseline and candidate require identical frame times")
  validate_time_grid(baseline_frames, spec.dt_s)
  validate_time_grid(candidate_frames, spec.dt_s)
  changed = sorted(
    name for name in set(baseline_params) | set(candidate_params)
    if baseline_params.get(name) != candidate_params.get(name)
  )
  read_names = {name for frame in candidate_frames for name in frame.read_parameters}
  effect = _trace_differs(baseline_frames, candidate_frames)
  coverage = {
    name: ParameterCoverage(
      read=name in read_names,
      trace_effect=effect and name in read_names,
      observable=effect and name in read_names,
    )
    for name in changed
  }
  credited = tuple(name for name in changed if coverage[name].observable)
  return ComparisonRun(
    spec=spec,
    baseline_frames=baseline_frames,
    candidate_frames=candidate_frames,
    parameter_coverage=coverage,
    credited_changes=credited,
    cache_key=comparison_cache_key(spec),
  )
