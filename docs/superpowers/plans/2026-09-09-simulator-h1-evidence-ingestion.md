# Simulator H1 Evidence Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a simulator-side, versioned H1 evidence contract that ingests normalized `carrotH1ReplayTrace`/`carrotH1ConfigSnapshot` records, validates provenance/sequence/config/radar identities, and exposes explicit H0/H1 HOLD conditions instead of guessing missing data.

**Architecture:** The public simulator does not import or vendor the full Carrot/openpilot tree. A small pure-Python evidence module accepts normalized JSON records exported from route data, validates schema version 6 and deterministic identities, and produces replay-ready immutable records plus a qualification summary. openpilot-specific capnp extraction remains outside the simulator core behind an adapter/export step.

**Tech Stack:** Python 3.11+, standard library only (`dataclasses`, `hashlib`, `json`, `pathlib`, `typing`), existing `unittest` suite.

**Spec:** `docs/superpowers/specs/2026-09-09-carrot-observability-simulator-boundary-design.md`

## Global Constraints

- No dependency on eGPU, Guardian, BIG/SMALL model infrastructure, or openpilot runtime modules.
- Public simulator code must not write to a live vehicle or comma Params.
- H1 schema version `6` is accepted; unsupported versions are explicit HOLD/error conditions.
- Missing config/radar/trigger identity must never be silently reconstructed from approximate timestamps.
- Raw rlog/qlog without the required H1 records may still be usable for H0/H2 research, but must not be promoted to deterministic H1 controller-replay evidence.
- All fixtures committed to the public repository are synthetic and contain no real route/device identity.

---

### Task 1: Define immutable H1 record contracts

**Files:**
- Create: `carrot_sim/h1_evidence.py`
- Create: `tests/test_h1_evidence.py`

**Interfaces:**
- Consumes: Python dictionaries decoded from normalized JSON records.
- Produces: `H1ReplayTrace`, `H1ConfigSnapshot`, `H1EvidenceError`, and parsing functions `parse_replay_trace()` / `parse_config_snapshot()`.

- [ ] **Step 1: Write failing schema/version tests**

```python
import unittest

from carrot_sim.h1_evidence import H1EvidenceError, parse_config_snapshot, parse_replay_trace


class TestH1EvidenceParsing(unittest.TestCase):
  def test_rejects_unsupported_trace_schema(self):
    row = valid_trace_dict()
    row["schemaVersion"] = 7
    with self.assertRaisesRegex(H1EvidenceError, "unsupported H1 replay schema"):
      parse_replay_trace(row)

  def test_rejects_missing_snapshot_identity(self):
    row = valid_trace_dict()
    row.pop("consumedSnapshotIdentitySha256")
    with self.assertRaisesRegex(H1EvidenceError, "consumedSnapshotIdentitySha256"):
      parse_replay_trace(row)
```

The test file must define `valid_trace_dict()` and `valid_config_dict()` with synthetic values only.

- [ ] **Step 2: Run the test and verify module import fails**

Run: `python -m unittest -v tests.test_h1_evidence`

Expected: FAIL because `carrot_sim.h1_evidence` does not exist.

- [ ] **Step 3: Implement the record types and strict parsing helpers**

```python
from dataclasses import dataclass
from typing import Any

H1_SCHEMA_VERSION = 6

class H1EvidenceError(ValueError):
  pass

@dataclass(frozen=True)
class H1ReplayTrace:
  schema_version: int
  process_epoch: int
  loop_sequence: int
  planner_cycle: int
  submaster_frame: int
  planning_trigger_kind: int
  planning_trigger_log_mono_time: int
  config_sequence: int
  config_sha256: str
  radar_input_kind: int
  effective_radar_state_sha256: str
  consumed_snapshot_identity_sha256: str
  run_longitudinal: bool
  longitudinal_plan_emitted: bool

@dataclass(frozen=True)
class H1ConfigSnapshot:
  schema_version: int
  process_epoch: int
  config_sequence: int
  config_sha256: str
  canonical_json_utf8: bytes
```

Parsing rules:
- integer fields must reject bools;
- SHA fields must be exactly 64 lowercase/uppercase hex characters after normalization to lowercase, except `configSha256`/`effectiveRadarStateSha256` may be empty only when `longitudinalPlanEmitted` is false;
- `planningTriggerKind` must be `0` (`modelV2`) or `1` (`liveTracks`);
- `radarInputKind` must be `0`, `1`, or `2`;
- unsupported schema raises `H1EvidenceError`.

- [ ] **Step 4: Run focused tests**

Run: `python -m unittest -v tests.test_h1_evidence`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add carrot_sim/h1_evidence.py tests/test_h1_evidence.py
git commit -m "feat: define strict H1 evidence contracts"
```

---

### Task 2: Verify config snapshot identity from canonical bytes

**Files:**
- Modify: `carrot_sim/h1_evidence.py`
- Modify: `tests/test_h1_evidence.py`

**Interfaces:**
- Consumes: `H1ConfigSnapshot.canonical_json_utf8` and declared SHA.
- Produces: `verify_config_snapshot(snapshot) -> None`, raising `H1EvidenceError` on mismatch/non-canonical JSON.

- [ ] **Step 1: Write failing identity tests**

```python
import hashlib
import json


def test_config_snapshot_hash_mismatch(self):
  row = valid_config_dict()
  row["configSha256"] = "00" * 32
  snapshot = parse_config_snapshot(row)
  with self.assertRaisesRegex(H1EvidenceError, "config hash mismatch"):
    verify_config_snapshot(snapshot)


def test_config_snapshot_accepts_canonical_json(self):
  payload = json.dumps({"appliedConfig": {"tFollowGap1": 1.1}}, sort_keys=True, separators=(",", ":")).encode()
  row = valid_config_dict(payload=payload, digest=hashlib.sha256(payload).hexdigest())
  verify_config_snapshot(parse_config_snapshot(row))
```

- [ ] **Step 2: Run and verify failure because verifier is absent**

Run: `python -m unittest -v tests.test_h1_evidence.TestH1EvidenceParsing.test_config_snapshot_hash_mismatch`

Expected: FAIL.

- [ ] **Step 3: Implement exact hash and canonical JSON verification**

```python
def verify_config_snapshot(snapshot: H1ConfigSnapshot) -> None:
  digest = hashlib.sha256(snapshot.canonical_json_utf8).hexdigest()
  if digest != snapshot.config_sha256:
    raise H1EvidenceError("config hash mismatch")
  decoded = json.loads(snapshot.canonical_json_utf8.decode("utf-8"))
  canonical = json.dumps(decoded, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
  if canonical != snapshot.canonical_json_utf8:
    raise H1EvidenceError("config payload is not canonical JSON")
```

- [ ] **Step 4: Run all H1 evidence tests**

Run: `python -m unittest -v tests.test_h1_evidence`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add carrot_sim/h1_evidence.py tests/test_h1_evidence.py
git commit -m "feat: verify H1 config snapshot identity"
```

---

### Task 3: Build an evidence-set validator

**Files:**
- Create: `carrot_sim/h1_evidence_set.py`
- Create: `tests/test_h1_evidence_set.py`

**Interfaces:**
- Consumes: sequences of `H1ReplayTrace` and `H1ConfigSnapshot`.
- Produces: `H1EvidenceQualification(status, reasons, trace_count, planner_cycle_count, config_count)` where status is `H1_READY` or `H1_HOLD`.

- [ ] **Step 1: Write failing sequence/config-link tests**

```python
import unittest
from carrot_sim.h1_evidence_set import qualify_h1_evidence


class TestH1EvidenceSet(unittest.TestCase):
  def test_gap_in_loop_sequence_holds(self):
    traces = [trace(loop_sequence=1), trace(loop_sequence=3)]
    result = qualify_h1_evidence(traces, configs=[config(sequence=1)])
    self.assertEqual(result.status, "H1_HOLD")
    self.assertIn("LOOP_SEQUENCE_GAP", result.reasons)

  def test_emitted_plan_requires_matching_config(self):
    traces = [trace(loop_sequence=1, emitted=True, config_sequence=4, config_sha="11" * 32)]
    result = qualify_h1_evidence(traces, configs=[])
    self.assertEqual(result.status, "H1_HOLD")
    self.assertIn("MISSING_CONFIG_SNAPSHOT", result.reasons)
```

- [ ] **Step 2: Run and verify import failure**

Run: `python -m unittest -v tests.test_h1_evidence_set`

Expected: FAIL.

- [ ] **Step 3: Implement qualification rules**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class H1EvidenceQualification:
  status: str
  reasons: tuple[str, ...]
  trace_count: int
  planner_cycle_count: int
  config_count: int
```

Rules, evaluated deterministically:
1. no trace records -> `NO_H1_TRACE`;
2. mixed `process_epoch` -> `MIXED_PROCESS_EPOCH` unless the caller has already split evidence by process;
3. non-increasing or gapped `loop_sequence` -> `LOOP_SEQUENCE_GAP`;
4. `planner_cycle` may remain constant on non-emitted loops but must not decrease or jump by more than one when `longitudinal_plan_emitted` is true -> `PLANNER_CYCLE_INVALID`;
5. emitted plans require non-empty config and radar SHA identities -> `MISSING_EFFECTIVE_IDENTITY`;
6. every emitted trace's `(config_sequence, config_sha256)` must match a verified config snapshot in the same process epoch -> `MISSING_CONFIG_SNAPSHOT` or `CONFIG_IDENTITY_MISMATCH`;
7. duplicate config sequence with different SHA -> `CONFIG_SEQUENCE_COLLISION`;
8. if no reasons remain -> `H1_READY`.

- [ ] **Step 4: Run tests**

Run: `python -m unittest -v tests.test_h1_evidence_set`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add carrot_sim/h1_evidence_set.py tests/test_h1_evidence_set.py
git commit -m "feat: qualify deterministic H1 evidence sets"
```

---

### Task 4: Add normalized JSONL ingestion/export boundary

**Files:**
- Create: `carrot_sim/h1_jsonl.py`
- Create: `scripts/inspect_h1_evidence.py`
- Create: `tests/test_h1_jsonl.py`

**Interfaces:**
- Consumes: newline-delimited JSON objects with top-level `type` equal to `carrotH1ReplayTrace` or `carrotH1ConfigSnapshot`.
- Produces: `load_h1_jsonl(path) -> tuple[list[H1ReplayTrace], list[H1ConfigSnapshot]]` and CLI JSON qualification summary.

- [ ] **Step 1: Write failing mixed-record ingestion test**

```python
import json
from pathlib import Path
import tempfile
import unittest

from carrot_sim.h1_jsonl import load_h1_jsonl


class TestH1Jsonl(unittest.TestCase):
  def test_loads_trace_and_config_records(self):
    with tempfile.TemporaryDirectory() as td:
      path = Path(td) / "h1.jsonl"
      path.write_text("\n".join([
        json.dumps({"type": "carrotH1ConfigSnapshot", "data": valid_config_dict()}),
        json.dumps({"type": "carrotH1ReplayTrace", "data": valid_trace_dict()}),
      ]) + "\n")
      traces, configs = load_h1_jsonl(path)
      self.assertEqual(len(traces), 1)
      self.assertEqual(len(configs), 1)
```

- [ ] **Step 2: Run and verify import failure**

Run: `python -m unittest -v tests.test_h1_jsonl`

Expected: FAIL.

- [ ] **Step 3: Implement strict JSONL loading**

Loader behavior:
- blank lines ignored;
- malformed JSON raises `H1EvidenceError` with 1-based line number;
- unknown `type` raises rather than silently dropping;
- missing `data` raises;
- config snapshots are verified with `verify_config_snapshot` before return;
- no openpilot/capnp import is permitted.

- [ ] **Step 4: Implement CLI summary**

`inspect_h1_evidence.py PATH` prints one JSON object containing:

```json
{
  "status": "H1_READY",
  "reasons": [],
  "traceCount": 1,
  "plannerCycleCount": 1,
  "configCount": 1
}
```

Exit code is `0` for `H1_READY`, `2` for `H1_HOLD`, and `3` for malformed/unsupported evidence.

- [ ] **Step 5: Run tests and commit**

```bash
python -m unittest -v tests.test_h1_jsonl tests.test_h1_evidence tests.test_h1_evidence_set
git add carrot_sim/h1_jsonl.py scripts/inspect_h1_evidence.py tests/test_h1_jsonl.py
git commit -m "feat: ingest normalized H1 replay evidence"
```

---

### Task 5: Add synthetic fixtures demonstrating READY and HOLD cases

**Files:**
- Create: `examples/h1_evidence_ready.jsonl`
- Create: `examples/h1_evidence_missing_config.jsonl`
- Create: `tests/test_h1_examples.py`

**Interfaces:**
- Consumes: only synthetic example evidence.
- Produces: reproducible CLI demonstrations and regression fixtures.

- [ ] **Step 1: Write failing example regression test**

```python
from pathlib import Path
import unittest

from carrot_sim.h1_jsonl import load_h1_jsonl
from carrot_sim.h1_evidence_set import qualify_h1_evidence


class TestH1Examples(unittest.TestCase):
  def test_ready_example_is_ready(self):
    traces, configs = load_h1_jsonl(Path("examples/h1_evidence_ready.jsonl"))
    self.assertEqual(qualify_h1_evidence(traces, configs).status, "H1_READY")

  def test_missing_config_example_holds(self):
    traces, configs = load_h1_jsonl(Path("examples/h1_evidence_missing_config.jsonl"))
    result = qualify_h1_evidence(traces, configs)
    self.assertEqual(result.status, "H1_HOLD")
    self.assertIn("MISSING_CONFIG_SNAPSHOT", result.reasons)
```

- [ ] **Step 2: Run and verify missing example files fail**

Run: `python -m unittest -v tests.test_h1_examples`

Expected: FAIL with missing file errors.

- [ ] **Step 3: Create deterministic synthetic examples**

Use process epoch `1000000`, loop sequences `1,2`, planner cycles `1,1`, and a canonical config payload such as `{"appliedConfig":{"tFollowGap1":1.1},"rawParams":{}}`. Compute the exact SHA256 of the UTF-8 canonical bytes and use that same digest in the emitted trace and config snapshot. Use a distinct fixed 64-hex radar digest for the emitted trace.

- [ ] **Step 4: Run tests and both CLI examples**

```bash
python -m unittest -v tests.test_h1_examples
python scripts/inspect_h1_evidence.py examples/h1_evidence_ready.jsonl
python scripts/inspect_h1_evidence.py examples/h1_evidence_missing_config.jsonl
```

Expected: first CLI exit `0`/`H1_READY`; second exit `2`/`H1_HOLD` with `MISSING_CONFIG_SNAPSHOT`.

- [ ] **Step 5: Commit**

```bash
git add examples/h1_evidence_ready.jsonl examples/h1_evidence_missing_config.jsonl tests/test_h1_examples.py
git commit -m "test: add synthetic H1 evidence examples"
```

---

### Task 6: Document the H0/H1 boundary in the public README

**Files:**
- Modify: `README.md`
- Modify: `README_EN.md`
- Create: `docs/H1_OBSERVABILITY_KO.md`

**Interfaces:**
- Consumes: implemented H1 evidence parser/qualification behavior.
- Produces: user-facing explanation of what extra instrumentation is for and what it does not prove.

- [ ] **Step 1: Add Korean H1 observability documentation**

The document must state:
- normal `rlog/qlog` remains the primary route evidence;
- H1 trace/config records exist only to preserve planner-consumed loop/config/radar identity that can otherwise be ambiguous in replay;
- `H1_READY` means the evidence set is structurally sufficient for deterministic replay work, not that the controller or vehicle is safe;
- missing/unsupported H1 evidence yields `H1_HOLD` rather than inferred values;
- the public simulator does not modify live control.

- [ ] **Step 2: Update README status/roadmap**

Change `실주행 관측성(Observability)` from a vague research item to reference the new normalized evidence contract and `docs/H1_OBSERVABILITY_KO.md`. Keep `종방향(Longitudinal) 모델` as research-in-progress until H1/H2 validation is actually complete.

- [ ] **Step 3: Update English README with the same boundary**

Use the same factual claims and statuses; do not mark H1 replay fidelity complete until real route evidence passes.

- [ ] **Step 4: Run the full public test suite**

Run: `python -m unittest discover -s tests -p 'test_*.py' -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md README_EN.md docs/H1_OBSERVABILITY_KO.md
git commit -m "docs: define H1 observability evidence boundary"
```

---

### Task 7: Integrate real exported evidence only after the comma overlay is verified

**Files:**
- Do not commit real route data to the public repository.
- Real normalized export should be stored in the private evidence location selected for the project.

**Interfaces:**
- Consumes: route data from the verified comma overlay.
- Produces: a private H1 qualification report and the first real replay-fidelity dataset.

- [ ] **Step 1: Export `carrotH1ReplayTrace` and `carrotH1ConfigSnapshot` to the normalized JSONL envelope**

Each line must be exactly one of:

```json
{"type":"carrotH1ReplayTrace","data":{}}
```

or

```json
{"type":"carrotH1ConfigSnapshot","data":{}}
```

with all schema-v6 fields represented faithfully; SHA bytes are encoded as lowercase hex and `canonicalJsonUtf8` as UTF-8 text or a clearly versioned byte encoding chosen by the exporter.

- [ ] **Step 2: Run public structural qualification against the private export**

```bash
python scripts/inspect_h1_evidence.py /private/path/to/h1.jsonl
```

If status is `H1_HOLD`, preserve the reasons and fix the exporter/instrumentation; do not infer missing identities.

- [ ] **Step 3: Only after `H1_READY`, connect the resulting records to the controller replay harness**

The first replay acceptance metric is equality/reproducibility of controller inputs/config identities and planner outputs on recorded cycles. Vehicle-plant fitting remains a separate H2 step.
