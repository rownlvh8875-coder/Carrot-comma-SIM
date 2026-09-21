#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from carrot_sim.campaign_manifest import canonical_json
from carrot_sim.driving_distribution import distribution_model_from_artifact
from carrot_sim.learned_scenario_generator import ScenarioGeneratorConfig, generate_scenario_pack


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--model", required=True)
  parser.add_argument("--output", required=True)
  parser.add_argument("--seed", required=True)
  parser.add_argument("--count", required=True, type=int)
  parser.add_argument("--families", required=True)
  args = parser.parse_args()
  artifact = json.loads(Path(args.model).read_text(encoding="utf-8"))
  model = distribution_model_from_artifact(artifact)
  config = ScenarioGeneratorConfig(tuple(item.strip() for item in args.families.split(",") if item.strip()))
  rows = generate_scenario_pack(model, config, args.seed, args.count)
  destination = Path(args.output)
  destination.parent.mkdir(parents=True, exist_ok=True)
  with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as handle:
    temporary = Path(handle.name)
    for row in rows:
      handle.write(canonical_json(row.to_artifact()) + "\n")
    handle.flush()
  temporary.replace(destination)
  print(canonical_json({"count": len(rows), "output": str(destination), "real_vehicle_write": False}))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
