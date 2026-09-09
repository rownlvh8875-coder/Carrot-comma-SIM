# Openpilot H1 Observability Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract only the H1 replay observability changes from the historical v6/eGPU migration and maintain them as a small, control-neutral overlay on normal `carrot-wip`.

**Architecture:** `ajouatom/openpilot:carrot-wip` remains the authoritative driving software. The overlay is limited to schema/service registration, loop/config/radar observation, and minimal read hooks needed to record the exact state consumed by planning. eGPU, Guardian, model-slot, telemetry, shadow-runner, panda, actuator, and alternate-control changes are excluded.

**Tech Stack:** Python 3.12+, Cap'n Proto cereal schemas, openpilot messaging/SubMaster/PubMaster, Git/GitHub, unittest/pytest as already used by the upstream tree.

**Spec:** `docs/superpowers/specs/2026-09-09-carrot-observability-simulator-boundary-design.md`

## Global Constraints

- Live vehicle software continues to follow normal `carrot-wip`; this project does not own or approve upstream control releases.
- The overlay must not change steering, braking, acceleration policy, panda safety, actuator limits, model selection, or control authorization.
- Observability failure must be fail-open for driving: trace/config serialization or publication failure cannot terminate or alter the planning loop.
- The retained H1 schema version is `6` until a deliberate version bump is designed and simulator support is added.
- No eGPU runtime/build dependency is allowed in the clean observability path.
- The historical source commit `6383e0cda19f7d9bfeddb6a7732a6da764cca3da` is evidence to mine, not a base branch.
- The live comma working tree is not modified until its exact branch/HEAD/dirty diff is captured read-only.

---

### Task 1: Freeze the historical H1 overlay inventory

**Files:**
- Create in `Carrot-comma-SIM`: `integration/openpilot/h1_overlay_manifest.json`
- Create in `Carrot-comma-SIM`: `tests/test_h1_overlay_manifest.py`

**Interfaces:**
- Consumes: historical migration commit `6383e0cda19f7d9bfeddb6a7732a6da764cca3da`.
- Produces: a machine-readable allowlist of overlay paths and classifications used by later compatibility/extraction tasks.

- [ ] **Step 1: Write the failing manifest test**

```python
import json
from pathlib import Path
import unittest


class TestH1OverlayManifest(unittest.TestCase):
  def test_manifest_contains_only_observability_paths(self):
    data = json.loads(Path("integration/openpilot/h1_overlay_manifest.json").read_text())
    self.assertEqual(data["schemaVersion"], 1)
    self.assertEqual(data["historicalSourceCommit"], "6383e0cda19f7d9bfeddb6a7732a6da764cca3da")
    forbidden = ("egpu", "guardian", "shadow", "model_slot", "telemetry")
    for entry in data["paths"]:
      lower = entry["path"].lower()
      self.assertFalse(any(token in lower for token in forbidden), entry)
      self.assertIn(entry["classification"], {"REQUIRED", "OPTIONAL_RADAR_DECODE"})

  def test_expected_required_paths_are_present(self):
    data = json.loads(Path("integration/openpilot/h1_overlay_manifest.json").read_text())
    paths = {entry["path"] for entry in data["paths"] if entry["classification"] == "REQUIRED"}
    self.assertEqual(paths, {
      "openpilot/cereal/custom.capnp",
      "openpilot/cereal/log.capnp",
      "openpilot/cereal/services.py",
      "openpilot/selfdrive/carrot/carrot_functions.py",
      "openpilot/selfdrive/controls/lib/h1_observability.py",
      "openpilot/selfdrive/controls/lib/longitudinal_planner.py",
      "openpilot/selfdrive/controls/plannerd.py",
    })
```

- [ ] **Step 2: Run the test and verify it fails because the manifest does not exist**

Run: `python -m unittest -v tests.test_h1_overlay_manifest`

Expected: FAIL with `FileNotFoundError` for `integration/openpilot/h1_overlay_manifest.json`.

- [ ] **Step 3: Create the minimal manifest**

```json
{
  "schemaVersion": 1,
  "historicalSourceCommit": "6383e0cda19f7d9bfeddb6a7732a6da764cca3da",
  "historicalLiveBase": "ce3d76301c988db8aa955e1ebc6496f0a0fd2abc",
  "h1SchemaVersion": 6,
  "paths": [
    {"path": "openpilot/cereal/custom.capnp", "classification": "REQUIRED"},
    {"path": "openpilot/cereal/log.capnp", "classification": "REQUIRED"},
    {"path": "openpilot/cereal/services.py", "classification": "REQUIRED"},
    {"path": "openpilot/selfdrive/carrot/carrot_functions.py", "classification": "REQUIRED"},
    {"path": "openpilot/selfdrive/controls/lib/h1_observability.py", "classification": "REQUIRED"},
    {"path": "openpilot/selfdrive/controls/lib/longitudinal_planner.py", "classification": "REQUIRED"},
    {"path": "openpilot/selfdrive/controls/plannerd.py", "classification": "REQUIRED"},
    {"path": "opendbc_repo/opendbc/dbc/generator/hyundai/hyundai_canfd_radar.dbc", "classification": "OPTIONAL_RADAR_DECODE"}
  ],
  "explicitlyExcludedHistoricalPaths": [
    ".github/workflows/egpu-integrated-ci.yml"
  ]
}
```

- [ ] **Step 4: Run the test and verify it passes**

Run: `python -m unittest -v tests.test_h1_overlay_manifest`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add integration/openpilot/h1_overlay_manifest.json tests/test_h1_overlay_manifest.py
git commit -m "test: freeze minimal H1 observability overlay inventory"
```

---

### Task 2: Add a fail-closed upstream compatibility checker

**Files:**
- Create in `Carrot-comma-SIM`: `carrot_sim/openpilot_overlay_compat.py`
- Create in `Carrot-comma-SIM`: `tests/test_openpilot_overlay_compat.py`
- Create in `Carrot-comma-SIM`: `scripts/check_openpilot_overlay.py`

**Interfaces:**
- Consumes: an openpilot checkout root and `h1_overlay_manifest.json`.
- Produces: `OverlayCompatibilityReport(status, missing_paths, missing_anchors, forbidden_paths)` with status `COMPATIBLE`, `REVIEW_REQUIRED`, or `INVALID_SOURCE`.

- [ ] **Step 1: Write failing compatibility tests**

```python
from pathlib import Path
import tempfile
import unittest

from carrot_sim.openpilot_overlay_compat import inspect_openpilot_overlay_source


class TestOverlayCompat(unittest.TestCase):
  def test_missing_required_path_is_invalid_source(self):
    with tempfile.TemporaryDirectory() as td:
      report = inspect_openpilot_overlay_source(Path(td))
      self.assertEqual(report.status, "INVALID_SOURCE")
      self.assertTrue(report.missing_paths)

  def test_forbidden_egpu_file_is_reported(self):
    with tempfile.TemporaryDirectory() as td:
      root = Path(td)
      for rel in REQUIRED_FIXTURE_PATHS:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(REQUIRED_FIXTURE_CONTENT[rel])
      bad = root / "openpilot/selfdrive/modeld/egpu_integrated_guardian.py"
      bad.parent.mkdir(parents=True, exist_ok=True)
      bad.write_text("# forbidden")
      report = inspect_openpilot_overlay_source(root)
      self.assertIn(str(bad.relative_to(root)), report.forbidden_paths)
```

The test fixture constants must contain the exact anchor strings defined in Step 3 below.

- [ ] **Step 2: Run the tests to verify they fail because the module does not exist**

Run: `python -m unittest -v tests.test_openpilot_overlay_compat`

Expected: import failure for `carrot_sim.openpilot_overlay_compat`.

- [ ] **Step 3: Implement deterministic source inspection**

```python
from dataclasses import dataclass
from pathlib import Path

REQUIRED_ANCHORS = {
  "openpilot/cereal/custom.capnp": ("struct CarrotNaviMedia",),
  "openpilot/cereal/log.capnp": ("struct Event",),
  "openpilot/cereal/services.py": ("\"longitudinalPlan\"",),
  "openpilot/selfdrive/carrot/carrot_functions.py": ("class CarrotPlanner",),
  "openpilot/selfdrive/controls/lib/longitudinal_planner.py": ("class LongitudinalPlanner",),
  "openpilot/selfdrive/controls/plannerd.py": ("def plannerd_thread",),
}
FORBIDDEN_NAME_TOKENS = ("egpu", "guardian", "shadow_probe", "model_slot")

@dataclass(frozen=True)
class OverlayCompatibilityReport:
  status: str
  missing_paths: tuple[str, ...]
  missing_anchors: tuple[str, ...]
  forbidden_paths: tuple[str, ...]


def inspect_openpilot_overlay_source(root: Path) -> OverlayCompatibilityReport:
  missing_paths = []
  missing_anchors = []
  for rel, anchors in REQUIRED_ANCHORS.items():
    path = root / rel
    if not path.is_file():
      missing_paths.append(rel)
      continue
    text = path.read_text(encoding="utf-8")
    for anchor in anchors:
      if anchor not in text:
        missing_anchors.append(f"{rel}:{anchor}")

  forbidden_paths = []
  for path in root.rglob("*"):
    if path.is_file() and any(token in path.name.lower() for token in FORBIDDEN_NAME_TOKENS):
      forbidden_paths.append(str(path.relative_to(root)))

  if missing_paths:
    status = "INVALID_SOURCE"
  elif missing_anchors or forbidden_paths:
    status = "REVIEW_REQUIRED"
  else:
    status = "COMPATIBLE"
  return OverlayCompatibilityReport(status, tuple(missing_paths), tuple(missing_anchors), tuple(sorted(forbidden_paths)))
```

- [ ] **Step 4: Add the CLI wrapper and run tests**

`check_openpilot_overlay.py` must accept one positional checkout path, call `inspect_openpilot_overlay_source`, serialize the dataclass with `json.dumps(asdict(report), sort_keys=True)`, and exit `0` only for `COMPATIBLE`; `2` otherwise.

Run: `python -m unittest -v tests.test_openpilot_overlay_compat`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add carrot_sim/openpilot_overlay_compat.py tests/test_openpilot_overlay_compat.py scripts/check_openpilot_overlay.py
git commit -m "feat: add H1 overlay source compatibility gate"
```

---

### Task 3: Create the clean openpilot extraction branch from the current upstream revision

**Files:**
- Modify in `rownlvh8875-coder/openpilot` only on a new temporary branch: the seven required paths from Task 1.
- Optional: `opendbc_repo/opendbc/dbc/generator/hyundai/hyundai_canfd_radar.dbc` only if current upstream does not already contain an equivalent required decoder.
- Do not modify `.github/workflows/egpu-integrated-ci.yml`.

**Interfaces:**
- Consumes: exact current `ajouatom/openpilot:carrot-wip` HEAD and the historical H1 patches.
- Produces: a branch whose diff from upstream contains only H1 observability and optional radar-decode support.

- [ ] **Step 1: Record exact upstream identity before creating the branch**

```bash
git fetch upstream carrot-wip
git rev-parse upstream/carrot-wip
git status --short
```

Expected: an exact SHA printed and no working-tree mutation caused by the inspection.

- [ ] **Step 2: Create the extraction branch from that exact upstream SHA**

```bash
git switch --detach upstream/carrot-wip
git switch -c sim-h1-observability-v1
```

- [ ] **Step 3: Reimplement only the schema/service/helper hooks from historical commit `6383e0cd...`**

Required behavior:
- `carrotH1ReplayTrace` and `carrotH1ConfigSnapshot` occupy the historical custom event slots and declare schema version 6.
- `services.py` logs the two H1 services.
- `H1Observability` records loop sequence, SubMaster receive identity, planning trigger, config identity, and effective radar identity.
- `CarrotPlanner` and `LongitudinalPlanner` record raw Params they actually consume without changing the resulting values.
- `plannerd.py` calls the observer after planning state is known, not before inputs are consumed.

Do not copy any eGPU import, file, environment flag, marker, telemetry, Guardian, model-contract, or shadow code.

- [ ] **Step 4: Verify the diff allowlist**

```bash
git diff --name-only upstream/carrot-wip...HEAD
```

Expected: only the seven required paths plus the optional Hyundai radar DBC.

Then run:

```bash
python /path/to/Carrot-comma-SIM/scripts/check_openpilot_overlay.py .
```

Expected: `COMPATIBLE` and exit code 0.

- [ ] **Step 5: Commit the extraction as one reviewable commit**

```bash
git add openpilot/cereal/custom.capnp openpilot/cereal/log.capnp openpilot/cereal/services.py \
  openpilot/selfdrive/carrot/carrot_functions.py \
  openpilot/selfdrive/controls/lib/h1_observability.py \
  openpilot/selfdrive/controls/lib/longitudinal_planner.py \
  openpilot/selfdrive/controls/plannerd.py
git commit -m "carrot: add control-neutral H1 replay observability"
```

Add the radar DBC to the same commit only if Step 3 established it is required and not already available upstream.

---

### Task 4: Add control-equivalence and observer-failure tests in openpilot

**Files:**
- Create: `openpilot/selfdrive/controls/tests/test_h1_observability_equivalence.py`
- Modify: `openpilot/selfdrive/controls/lib/h1_observability.py` only as needed to make publication failure fail-open.

**Interfaces:**
- Consumes: the clean overlay from Task 3.
- Produces: deterministic proof that observer enabled/disabled/failing states do not change the control-relevant planner result fixture.

- [ ] **Step 1: Write a failing helper-level fault isolation test**

```python
import unittest

from openpilot.selfdrive.controls.lib.h1_observability import H1Observability


class RaisingPM:
  def send(self, service, msg):
    raise RuntimeError("forced observer publish failure")


class TestH1ObserverFailureIsolation(unittest.TestCase):
  def test_publish_failure_disables_trace_without_raising(self):
    observer = H1Observability({})
    observer._safe_send(RaisingPM(), "carrotH1ReplayTrace", object())
    self.assertFalse(observer.enabled)
```

- [ ] **Step 2: Run the test and verify it fails because `_safe_send`/`enabled` are absent**

Run: `python -m unittest -v openpilot.selfdrive.controls.tests.test_h1_observability_equivalence`

Expected: FAIL.

- [ ] **Step 3: Implement fail-open publication**

`H1Observability.__init__` must set `self.enabled = True`. Add:

```python
def _safe_send(self, pm, service: str, msg) -> bool:
  if not self.enabled:
    return False
  try:
    pm.send(service, msg)
    return True
  except Exception:
    self.enabled = False
    return False
```

Replace direct `pm.send` calls for the two H1 messages with `_safe_send`. If `_safe_send` returns `False`, the observer returns without modifying planner/carrot/control state.

- [ ] **Step 4: Add deterministic output-equivalence fixture**

The test must execute the same longitudinal-planner fixture twice with identical inputs/Params: once with observer disabled and once enabled with a recording PubMaster. Assert equality for every control-relevant field emitted to `longitudinalPlan`, including target speeds/accelerations, shouldStop, FCW, source, and processing delay. A third execution uses `RaisingPM` and must match the disabled baseline exactly.

- [ ] **Step 5: Run focused and existing planner tests**

```bash
python -m unittest -v openpilot.selfdrive.controls.tests.test_h1_observability_equivalence
```

Expected: PASS.

Then run the repository's existing longitudinal/plannerd test targets that cover the touched files. Any failure is a stop condition; do not weaken existing tests.

- [ ] **Step 6: Commit**

```bash
git add openpilot/selfdrive/controls/lib/h1_observability.py openpilot/selfdrive/controls/tests/test_h1_observability_equivalence.py
git commit -m "test: prove H1 observer control equivalence and fail-open behavior"
```

---

### Task 5: Add daily-upstream rebase verification without owning Carrot control

**Files:**
- Create in `Carrot-comma-SIM`: `scripts/verify_h1_overlay_rebase.py`
- Create in `Carrot-comma-SIM`: `tests/test_verify_h1_overlay_rebase.py`
- Modify in `Carrot-comma-SIM`: `README.md`

**Interfaces:**
- Consumes: an upstream openpilot checkout and the clean overlay commit SHA.
- Produces: `FAST_COMPATIBILITY_PATH` when the overlay paths/anchors remain compatible, otherwise `REVALIDATION_REQUIRED`.

- [ ] **Step 1: Write the failing classification test**

```python
import unittest
from carrot_sim.openpilot_overlay_compat import classify_rebase_result


class TestRebaseClassification(unittest.TestCase):
  def test_compatible_source_uses_fast_path(self):
    self.assertEqual(classify_rebase_result("COMPATIBLE", conflicts=()), "FAST_COMPATIBILITY_PATH")

  def test_conflict_requires_revalidation(self):
    self.assertEqual(classify_rebase_result("COMPATIBLE", conflicts=("openpilot/selfdrive/controls/plannerd.py",)), "REVALIDATION_REQUIRED")
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest -v tests.test_verify_h1_overlay_rebase`

Expected: FAIL because `classify_rebase_result` is absent.

- [ ] **Step 3: Implement the classifier**

```python
def classify_rebase_result(source_status: str, conflicts: tuple[str, ...]) -> str:
  if source_status == "COMPATIBLE" and not conflicts:
    return "FAST_COMPATIBILITY_PATH"
  return "REVALIDATION_REQUIRED"
```

The CLI may perform read-only inspection or a disposable worktree/rebase simulation, but it must never update the live comma branch or reset the user's working tree.

- [ ] **Step 4: Update README operating policy**

Document:
- normal Carrot updates are not blocked by this project;
- `FAST_COMPATIBILITY_PATH` means only the observability overlay needs its normal regression suite;
- `REVALIDATION_REQUIRED` means one of the small hook/schema surfaces changed and must be reviewed;
- neither label is a safety approval of upstream Carrot behavior.

- [ ] **Step 5: Run simulator tests and commit**

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
git add carrot_sim/openpilot_overlay_compat.py scripts/verify_h1_overlay_rebase.py tests/test_verify_h1_overlay_rebase.py README.md
git commit -m "feat: add lightweight Carrot observability compatibility path"
```

---

### Task 6: Capture the live comma state read-only before any installation

**Files:**
- No repository file mutation during capture.
- Save the resulting text/JSON evidence outside `/data/openpilot` or in a designated evidence directory after confirming it cannot affect manager/openpilot startup.

**Interfaces:**
- Consumes: the actual comma device.
- Produces: exact branch/HEAD/remote/status/diff evidence used to decide whether the existing live H1 changes are already equivalent to the clean overlay.

- [ ] **Step 1: Capture repository identity**

```bash
cd /data/openpilot
git branch --show-current
git rev-parse HEAD
git remote -v
git status --short
git diff --stat
git diff --name-only
```

- [ ] **Step 2: Capture only the relevant diff without changing it**

```bash
git diff -- openpilot/cereal/custom.capnp openpilot/cereal/log.capnp openpilot/cereal/services.py \
  openpilot/selfdrive/carrot/carrot_functions.py \
  openpilot/selfdrive/controls/lib/h1_observability.py \
  openpilot/selfdrive/controls/lib/longitudinal_planner.py \
  openpilot/selfdrive/controls/plannerd.py
```

If the radar DBC is untracked/modified, record its path and hash separately.

- [ ] **Step 3: Classify every live non-upstream path**

Use exactly these labels:
- `OBSERVABILITY_REQUIRED`
- `SIMULATOR_OFFLINE`
- `UNRELATED`
- `REMOVE`

No file is removed in this task.

- [ ] **Step 4: Decide transition**

If the live observability diff is semantically identical to the clean overlay and the current upstream merge/rebase is clean, preserve it through the normal update path. If not, back up the current diff and install the clean overlay only while offroad.

---

### Task 7: Offroad device verification

**Files:**
- No new live-control code beyond the clean overlay already reviewed.

**Interfaces:**
- Consumes: comma running current `carrot-wip` plus clean H1 overlay.
- Produces: evidence that services boot, trace/config events appear, and observer failure does not destabilize normal processes.

- [ ] **Step 1: Boot with observer enabled but vehicle offroad**

Check manager/process state and confirm no new crash loop attributable to the overlay.

- [ ] **Step 2: Verify the two H1 services are registered and produce messages**

Confirm `carrotH1ReplayTrace` increments `loopSequence` and reports schema version 6. Confirm `carrotH1ConfigSnapshot` appears when the applied config identity changes.

- [ ] **Step 3: Exercise observer failure isolation offroad**

Use a test-only mechanism from the equivalence test or a disposable local invocation; do not corrupt the live logger. Confirm the observer can disable itself without stopping planning/manager processes.

- [ ] **Step 4: Resume road data collection only after offroad checks pass**

This step is not a claim of road-safety validation; it only confirms the instrumentation layer is not introducing an observed process/control-path regression.
