from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


UPSTREAM_HOST_ANCHORS = {
  "openpilot/cereal/custom.capnp": (
    "struct CustomReserved3 @0xda96579883444c35",
    "struct CustomReserved4 @0x80ae746ee2596b11",
  ),
  "openpilot/cereal/log.capnp": (
    "customReserved3 @110",
    "customReserved4 @111",
  ),
  "openpilot/cereal/services.py": (
    '"longitudinalPlan"',
  ),
  "openpilot/selfdrive/carrot/carrot_functions.py": (
    "class CarrotPlanner",
  ),
  "openpilot/selfdrive/controls/lib/longitudinal_planner.py": (
    "class LongitudinalPlanner",
  ),
  "openpilot/selfdrive/controls/plannerd.py": (
    "def main():",
  ),
}


@dataclass(frozen=True)
class OverlayCompatibilityReport:
  status: str
  missing_paths: tuple[str, ...]
  missing_anchors: tuple[str, ...]


def inspect_openpilot_overlay_source(root: Path | str) -> OverlayCompatibilityReport:
  source_root = Path(root)
  missing_paths: list[str] = []
  missing_anchors: list[str] = []

  for relative_path, anchors in UPSTREAM_HOST_ANCHORS.items():
    path = source_root / relative_path
    if not path.is_file():
      missing_paths.append(relative_path)
      continue

    try:
      text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
      missing_paths.append(relative_path)
      continue

    for anchor in anchors:
      if anchor not in text:
        missing_anchors.append(f"{relative_path}:{anchor}")

  if missing_paths:
    status = "INVALID_SOURCE"
  elif missing_anchors:
    status = "REVIEW_REQUIRED"
  else:
    status = "COMPATIBLE"

  return OverlayCompatibilityReport(
    status=status,
    missing_paths=tuple(missing_paths),
    missing_anchors=tuple(missing_anchors),
  )


def classify_rebase_result(source_status: str, conflicts: tuple[str, ...]) -> str:
  """Classify only H1 overlay maintenance effort, never upstream driving safety."""
  if source_status == "COMPATIBLE" and not conflicts:
    return "FAST_COMPATIBILITY_PATH"
  return "REVALIDATION_REQUIRED"
