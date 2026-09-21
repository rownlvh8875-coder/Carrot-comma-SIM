from __future__ import annotations

from dataclasses import dataclass

from .closed_loop_campaign_runner import ComparisonRun


@dataclass(frozen=True)
class SafetyPolicy:
  min_ttc_s: float
  min_following_distance_m: float
  min_accel_mps2: float
  max_abs_jerk_mps3: float
  max_abs_steering_command: float
  max_steering_saturation_frames: int
  max_abs_lateral_error_m: float
  max_abs_yaw_error_rad: float
  schema_version: int = 1

  def __post_init__(self) -> None:
    if self.min_ttc_s < 0.0 or self.min_following_distance_m < 0.0:
      raise ValueError("minimum safety thresholds must be non-negative")
    if self.min_accel_mps2 > 0.0:
      raise ValueError("min_accel_mps2 must be <= 0")
    if self.max_steering_saturation_frames < 0:
      raise ValueError("max_steering_saturation_frames must be >= 0")


@dataclass(frozen=True)
class SafetyDecision:
  eligible: bool
  reason_codes: tuple[str, ...]
  first_failure_frame: dict[str, int]
  margins: dict[str, float | None]
  real_vehicle_write: bool = False


_REASON_ORDER = (
  "COLLISION_PROXY",
  "MISSING_MIN_TTC",
  "MIN_TTC",
  "MISSING_FOLLOWING_DISTANCE",
  "FOLLOWING_DISTANCE",
  "EXCESSIVE_DECEL",
  "EXCESSIVE_JERK",
  "STEERING_SATURATION",
  "LATERAL_DIVERGENCE",
  "YAW_DIVERGENCE",
)


def evaluate_safety(run: ComparisonRun, policy: SafetyPolicy) -> SafetyDecision:
  frames = run.candidate_frames
  failures: dict[str, int] = {}

  def fail(code: str, index: int) -> None:
    failures.setdefault(code, index)

  saturated = 0
  for index, frame in enumerate(frames):
    if frame.collision:
      fail("COLLISION_PROXY", index)
    if frame.min_ttc_s is None:
      fail("MISSING_MIN_TTC", index)
    elif frame.min_ttc_s < policy.min_ttc_s:
      fail("MIN_TTC", index)
    if frame.following_distance_m is None:
      fail("MISSING_FOLLOWING_DISTANCE", index)
    elif frame.following_distance_m < policy.min_following_distance_m:
      fail("FOLLOWING_DISTANCE", index)
    if frame.accel_mps2 < policy.min_accel_mps2:
      fail("EXCESSIVE_DECEL", index)
    if abs(frame.jerk_mps3) > policy.max_abs_jerk_mps3:
      fail("EXCESSIVE_JERK", index)
    if abs(frame.steering_command) > policy.max_abs_steering_command:
      saturated += 1
    if abs(frame.lateral_error_m) > policy.max_abs_lateral_error_m:
      fail("LATERAL_DIVERGENCE", index)
    if abs(frame.yaw_error_rad) > policy.max_abs_yaw_error_rad:
      fail("YAW_DIVERGENCE", index)
  if saturated > policy.max_steering_saturation_frames:
    first = next(index for index, frame in enumerate(frames) if abs(frame.steering_command) > policy.max_abs_steering_command)
    fail("STEERING_SATURATION", first)

  ttc_values = [frame.min_ttc_s for frame in frames if frame.min_ttc_s is not None]
  distance_values = [frame.following_distance_m for frame in frames if frame.following_distance_m is not None]
  margins = {
    "min_ttc_s": min(ttc_values) - policy.min_ttc_s if ttc_values else None,
    "min_following_distance_m": min(distance_values) - policy.min_following_distance_m if distance_values else None,
    "min_accel_mps2": min(frame.accel_mps2 for frame in frames) - policy.min_accel_mps2,
    "max_abs_jerk_mps3": policy.max_abs_jerk_mps3 - max(abs(frame.jerk_mps3) for frame in frames),
    "max_abs_lateral_error_m": policy.max_abs_lateral_error_m - max(abs(frame.lateral_error_m) for frame in frames),
    "max_abs_yaw_error_rad": policy.max_abs_yaw_error_rad - max(abs(frame.yaw_error_rad) for frame in frames),
  }
  ordered = tuple(code for code in _REASON_ORDER if code in failures)
  return SafetyDecision(not ordered, ordered, failures, margins)
