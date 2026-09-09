from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from carrot_sim.h1_evidence import H1ConfigSnapshot, H1ReplayTrace


@dataclass(frozen=True)
class H1EvidenceQualification:
  status: str
  reasons: tuple[str, ...]
  trace_count: int
  planner_cycle_count: int
  config_count: int


def qualify_h1_evidence(
  traces: Iterable[H1ReplayTrace],
  configs: Iterable[H1ConfigSnapshot],
) -> H1EvidenceQualification:
  trace_list = list(traces)
  config_list = list(configs)
  reasons: list[str] = []

  def add_reason(reason: str) -> None:
    if reason not in reasons:
      reasons.append(reason)

  if not trace_list:
    add_reason("NO_H1_TRACE")

  trace_epochs = {trace.process_epoch for trace in trace_list}
  if len(trace_epochs) > 1:
    add_reason("MIXED_PROCESS_EPOCH")

  for previous, current in zip(trace_list, trace_list[1:]):
    if current.process_epoch == previous.process_epoch and current.loop_sequence != previous.loop_sequence + 1:
      add_reason("LOOP_SEQUENCE_GAP")

    if current.process_epoch != previous.process_epoch:
      continue
    if current.longitudinal_plan_emitted:
      if current.planner_cycle != previous.planner_cycle + 1:
        add_reason("PLANNER_CYCLE_INVALID")
    elif current.planner_cycle != previous.planner_cycle:
      add_reason("PLANNER_CYCLE_INVALID")

  configs_by_key: dict[tuple[int, int], set[str]] = {}
  for snapshot in config_list:
    key = (snapshot.process_epoch, snapshot.config_sequence)
    configs_by_key.setdefault(key, set()).add(snapshot.config_sha256)
  if any(len(shas) > 1 for shas in configs_by_key.values()):
    add_reason("CONFIG_SEQUENCE_COLLISION")

  for trace in trace_list:
    if not trace.longitudinal_plan_emitted:
      continue
    if not trace.config_sha256 or not trace.effective_radar_state_sha256:
      add_reason("MISSING_EFFECTIVE_IDENTITY")

    key = (trace.process_epoch, trace.config_sequence)
    matching_shas = configs_by_key.get(key)
    if not matching_shas:
      add_reason("MISSING_CONFIG_SNAPSHOT")
    elif trace.config_sha256 not in matching_shas:
      add_reason("CONFIG_IDENTITY_MISMATCH")

  status = "H1_READY" if not reasons else "H1_HOLD"
  return H1EvidenceQualification(
    status=status,
    reasons=tuple(reasons),
    trace_count=len(trace_list),
    planner_cycle_count=sum(1 for trace in trace_list if trace.longitudinal_plan_emitted),
    config_count=len(config_list),
  )
