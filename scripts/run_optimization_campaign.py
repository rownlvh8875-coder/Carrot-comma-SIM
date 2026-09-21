#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from carrot_sim.campaign_manifest import canonical_json
from carrot_sim.optimization_campaign import OptimizationCampaign


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--output", required=True)
  parser.add_argument("--manifest-hash", required=True)
  parser.add_argument("--settings")
  parser.add_argument("--max-workers", type=int, default=2)
  parser.add_argument("--resume", action="store_true")
  parser.add_argument("--phase")
  args = parser.parse_args()
  if args.resume:
    campaign = OptimizationCampaign.resume(args.output, args.manifest_hash)
  else:
    if not args.settings:
      parser.error("--settings is required when creating a campaign")
    campaign = OptimizationCampaign.create(
      args.output, args.manifest_hash, args.settings, max_workers=args.max_workers,
    )
  if args.phase:
    campaign.advance(args.phase)
  print(canonical_json(campaign.status().to_artifact()))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
