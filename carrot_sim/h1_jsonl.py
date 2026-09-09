from __future__ import annotations

import json
from pathlib import Path

from carrot_sim.h1_evidence import (
  H1ConfigSnapshot,
  H1EvidenceError,
  H1ReplayTrace,
  parse_config_snapshot,
  parse_replay_trace,
  verify_config_snapshot,
)


TRACE_TYPE = "carrotH1ReplayTrace"
CONFIG_TYPE = "carrotH1ConfigSnapshot"


def load_h1_jsonl(path: Path | str) -> tuple[list[H1ReplayTrace], list[H1ConfigSnapshot]]:
  source = Path(path)
  traces: list[H1ReplayTrace] = []
  configs: list[H1ConfigSnapshot] = []

  try:
    lines = source.read_text(encoding="utf-8").splitlines()
  except (OSError, UnicodeError) as exc:
    raise H1EvidenceError(f"cannot read H1 evidence: {source}") from exc

  for line_number, raw_line in enumerate(lines, start=1):
    if not raw_line.strip():
      continue
    try:
      envelope = json.loads(raw_line)
    except json.JSONDecodeError as exc:
      raise H1EvidenceError(f"malformed H1 JSON at line {line_number}") from exc
    if not isinstance(envelope, dict):
      raise H1EvidenceError(f"H1 record at line {line_number} must be an object")
    if "data" not in envelope:
      raise H1EvidenceError(f"missing data at line {line_number}")

    record_type = envelope.get("type")
    data = envelope["data"]
    try:
      if record_type == TRACE_TYPE:
        traces.append(parse_replay_trace(data))
      elif record_type == CONFIG_TYPE:
        snapshot = parse_config_snapshot(data)
        verify_config_snapshot(snapshot)
        configs.append(snapshot)
      else:
        raise H1EvidenceError(f"unknown H1 record type at line {line_number}: {record_type!r}")
    except H1EvidenceError as exc:
      if f"line {line_number}" in str(exc):
        raise
      raise H1EvidenceError(f"line {line_number}: {exc}") from exc

  return traces, configs
