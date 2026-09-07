"""Constant-acceleration forward motion, followed by rest at zero speed."""

from __future__ import annotations


def integrate_forward_motion(speed_mps: float, accel_mps2: float, dt_s: float) -> tuple[float, float]:
    """Return speed and distance; never integrate braking past the stop time.

    Acceleration remains the axis/request value in the caller's state. The
    zero-speed constraint affects motion only; it does not reset filter history.
    """
    moving_dt = min(dt_s, speed_mps / -accel_mps2) if accel_mps2 < 0.0 else dt_s
    next_speed = max(0.0, speed_mps + accel_mps2 * dt_s)
    distance = max(0.0, speed_mps * moving_dt + 0.5 * accel_mps2 * moving_dt * moving_dt)
    return next_speed, distance
