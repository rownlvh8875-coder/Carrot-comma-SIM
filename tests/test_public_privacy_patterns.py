from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "public_release_audit.py"
_SPEC = importlib.util.spec_from_file_location("public_release_audit", _SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
scan = _MODULE.scan


def write_payload(root: Path, name: str, payload: object) -> list[str]:
  (root / name).write_text(json.dumps(payload), encoding="utf-8")
  return scan(root)


def test_rejects_route_like_identifier(tmp_path: Path):
  route = "sample" + "--" + "d0ee75c630"
  assert write_payload(tmp_path, "route.json", {"route": route})


def test_rejects_user_home_and_desktop_host(tmp_path: Path):
  home = "/" + "home" + "/" + "user" + "/private.json"
  host = "DESK" + "TOP-" + "EXAMPLE"
  assert write_payload(tmp_path, "host.json", {"path": home, "host": host})


def test_rejects_device_identifier_field(tmp_path: Path):
  key = "device" + "Id"
  assert write_payload(tmp_path, "device.json", {key: "synthetic-device"})


def test_rejects_actual_setting_bounds(tmp_path: Path):
  setting = "Stop" + "Distance"
  payload = {setting: {"minimum": 500, "maximum": 700}}
  assert write_payload(tmp_path, "bounds.json", payload)


def test_rejects_private_fixed_event_count(tmp_path: Path):
  count = 49_000 + 652
  payload = {"scenario_" + "event_count": count}
  assert write_payload(tmp_path, "count.json", payload)


def test_allows_generalized_synthetic_metadata(tmp_path: Path):
  payload = {
    "scenario_event_count": 6,
    "parameters": {"following_gap": {"minimum": 1.2, "maximum": 2.4}},
    "authority": {"recommendation_authorized": False, "real_vehicle_write": False},
  }
  assert write_payload(tmp_path, "safe.json", payload) == []
