from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from carrot_sim.h1_evidence import H1EvidenceError  # noqa: E402
from carrot_sim.h1_evidence_set import qualify_h1_evidence  # noqa: E402
from carrot_sim.h1_jsonl import load_h1_jsonl  # noqa: E402


def _summary_dict(result) -> dict[str, object]:
  raw = asdict(result)
  return {
    "status": raw["status"],
    "reasons": list(raw["reasons"]),
    "traceCount": raw["trace_count"],
    "plannerCycleCount": raw["planner_cycle_count"],
    "configCount": raw["config_count"],
  }


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Validate normalized schema-v6 H1 replay evidence.")
  parser.add_argument("path", type=Path, help="Path to normalized H1 JSONL evidence")
  args = parser.parse_args(argv)

  try:
    traces, configs = load_h1_jsonl(args.path)
    result = qualify_h1_evidence(traces, configs)
  except H1EvidenceError as exc:
    print(json.dumps({"status": "H1_ERROR", "error": str(exc)}, sort_keys=True))
    return 3

  print(json.dumps(_summary_dict(result), sort_keys=True))
  return 0 if result.status == "H1_READY" else 2


if __name__ == "__main__":
  raise SystemExit(main())
