from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def _assert_finite(value: Any, path: str = "$") -> None:
  if isinstance(value, float) and not math.isfinite(value):
    raise ValueError(f"{path} must contain finite numbers")
  if isinstance(value, dict):
    for key, item in value.items():
      _assert_finite(item, f"{path}.{key}")
  elif isinstance(value, (list, tuple)):
    for index, item in enumerate(value):
      _assert_finite(item, f"{path}[{index}]")


def canonical_json(value: object) -> str:
  _assert_finite(value)
  return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def content_sha256(value: object) -> str:
  return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
