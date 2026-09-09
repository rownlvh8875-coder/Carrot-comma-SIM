from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from carrot_sim.openpilot_overlay_compat import inspect_openpilot_overlay_source  # noqa: E402


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(
    description="Read-only check that an openpilot checkout still exposes the H1 observability host surface.",
  )
  parser.add_argument("checkout", type=Path, help="Path to an openpilot checkout")
  args = parser.parse_args(argv)

  report = inspect_openpilot_overlay_source(args.checkout)
  payload = {
    "status": report.status,
    "missingPaths": list(report.missing_paths),
    "missingAnchors": list(report.missing_anchors),
  }
  print(json.dumps(payload, sort_keys=True))
  return 0 if report.status == "COMPATIBLE" else 2


if __name__ == "__main__":
  raise SystemExit(main())
