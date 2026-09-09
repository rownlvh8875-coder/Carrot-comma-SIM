# Carrot observability / simulator boundary design

Date: 2026-09-09
Status: design approved in chat; implementation not started

## 1. Purpose

Carrot-comma-SIM is the project source of truth. Its purpose is to reproduce and stress-test Carrot/openpilot control behavior with replay and closed-loop vehicle plants. The Carrot-WIP upstream itself is not our product and is not to be maintained as a separate long-lived control fork.

The only permitted in-vehicle modification is a minimal observability overlay required to capture information that normal rlog/qlog does not preserve well enough for H1 controller replay fidelity.

## 2. Repository responsibilities

### A. `ajouatom/openpilot:carrot-wip`

Role: upstream driving software and authoritative live control source.

Rules:
- Follow upstream normally.
- Do not gate ordinary upstream updates on this simulator project.
- Do not add simulator features to upstream control logic.
- Upstream control behavior remains authoritative.

### B. Live comma `/data/openpilot`

Role: run the normal `carrot-wip` branch plus the smallest possible local observability overlay when normal logs are insufficient.

The live device remains on `carrot-wip`; it does **not** move to `carrot-wip-integrated-v6`, an eGPU branch, or a new simulator control fork.

Allowed local differences:
- H1 replay trace/config snapshot message definitions and service registration.
- A small `H1Observability` helper.
- Minimal hooks that capture the exact controller inputs/config/trigger state consumed by the planning loop.
- Hyundai radar DBC material only when it is required to decode recorded radar evidence for replay.
- Tests/diagnostics proving that observability ON/OFF does not change control-relevant outputs.

Forbidden local differences:
- eGPU integration, BIG/SMALL model commissioning, Guardian, eGPU telemetry, model-slot activation, eGPU shadow runners.
- steering/braking/acceleration policy changes.
- panda safety or actuator-limit changes.
- alternate Carrot control algorithms maintained by this project.
- simulator-specific logic that changes the live driving decision.

`rownlvh8875-coder/openpilot` may retain a **reference copy/history** of the observability patch for review and recovery, but that reference is not a new live control mainline.

### C. `rownlvh8875-coder/Carrot-comma-SIM`

Role: main project.

Responsibilities:
- ingest rlog/qlog and H1 observability evidence;
- H0 provenance checks;
- H1 controller replay fidelity;
- H2 vehicle plant identification/validation;
- closed-loop simulation;
- deterministic scenario regression;
- compatibility adapters for upstream Carrot changes;
- public-safe synthetic/example artifacts only.

## 3. Data flow

```text
Carrot-WIP (live vehicle, authoritative control)
        |
        | normal rlog/qlog
        | + minimal local H1 observability overlay when required
        v
Offline evidence / route export
        |
        v
Carrot-comma-SIM
  H0 provenance
        v
  H1 replay fidelity
        v
  H2 vehicle plant
        v
  closed-loop / scenario regression
```

The simulator consumes Carrot evidence. It does not own Carrot's live control policy.

## 4. Observability contract

The existing `h1_observability.py` concept is retained because it records loop-level consumed state needed to reconstruct H1 replay. The final overlay must satisfy all of the following.

1. **Observation-only:** no steering, braking, acceleration or control authorization changes.
2. **Fail-open for driving:** an observability serialization/publish error must not crash or alter the live control path. The error may disable tracing and emit a diagnostic, but driving behavior remains the upstream behavior.
3. **No hidden tuning:** observability may record consumed Params/config, but does not change those values.
4. **Exact identity:** each trace must bind loop sequence, timestamps/receive state, planning trigger, relevant configuration identity and effective radar input identity sufficiently for replay.
5. **Versioned schema:** trace/config messages have an explicit schema version and replay code rejects unsupported versions rather than guessing.
6. **Minimal patch surface:** live hooks are limited to the files strictly needed to capture missing evidence.
7. **Control equivalence test:** the same fixture with observability disabled/enabled must produce identical control-relevant planner outputs.
8. **Fault-injection test:** forced trace/config publication failures must not change control-relevant outputs or terminate the planning loop.

## 5. What is retained from the prior v6/H1 work

Retain conceptually:
- `H1Observability` loop-level trace;
- consumed configuration snapshot/identity;
- effective radar input identity and trigger timing needed for deterministic replay;
- Hyundai radar DBC only if replay decoding requires it;
- H1 regression tests that prove the observer does not change controller results.

Do not automatically retain every file from `carrot-wip-integrated-v6`. The migration source commit `6383e0cda19f7d9bfeddb6a7732a6da764cca3da` is evidence to mine, not the new base branch. Its PR documents that the original comma source was `carrot-wip` at `ce3d76301c988db8aa955e1ebc6496f0a0fd2abc`, with six tracked local changes plus Hyundai radar DBC and `h1_observability.py`.

## 6. What happens to eGPU work

All eGPU-related work is retained only as historical/research branches and PR history. It is not deleted until the clean simulator/observability path is proven.

It is excluded from:
- the live comma update path;
- the simulator's required dependency graph;
- H0/H1/H2 acceptance criteria;
- future Carrot upstream compatibility decisions.

No new work is to be based on `carrot-wip-integrated-v6` unless explicitly requested for a separate eGPU research task.

## 7. Upstream update policy

The vehicle continues to use `carrot-wip` and follows normal upstream updates. The simulator project does not issue a separate `COMMA PULL OK` approval for upstream releases.

The observability overlay is not allowed to become a reason to freeze Carrot. Its maintenance workflow is:
1. before/after an upstream pull, record the upstream HEAD and current local observability diff;
2. if Git can preserve the local overlay without overlap, continue normally;
3. if upstream touches an observability hook or message contract, reapply/update only that small overlay against the new upstream source;
4. run control-equivalence and fault-isolation tests for the overlay;
5. update the simulator adapter only if the replay evidence contract changed.

A compatibility problem in the observer is an **observer maintenance issue**, not a reason to fork or redesign the upstream controller.

## 8. Implementation approach

Recommended approach: **clean-room extraction onto current upstream**.

Do not delete eGPU code out of the integrated branch and call the result clean. Instead:
1. read the actual comma working tree and record branch/HEAD/dirty diff before changing it;
2. fetch/pull the current upstream `carrot-wip` only after the local diff has been safely inventoried/backed up;
3. inspect the historical H1 migration and classify every local change;
4. reimplement/reapply only the minimum observability pieces on the normal `carrot-wip` tree;
5. add dedicated observer-isolation tests;
6. keep simulator-side replay/adapter logic in Carrot-comma-SIM;
7. validate on an offroad comma before normal vehicle use.

This minimizes the live patch surface and preserves the existing Carrot update workflow.

## 9. Implementation gates

### Gate A — source inventory
- exact live comma branch/HEAD/dirty diff recorded read-only;
- current upstream head recorded;
- every non-upstream live file classified as `OBSERVABILITY_REQUIRED`, `SIMULATOR_OFFLINE`, `UNRELATED`, or `REMOVE`;
- a recoverable copy of the pre-cleanup local diff exists before any reset/pull/reapply operation.

### Gate B — observer extraction
- eGPU dependency count = 0;
- no control/panda/actuator-policy changes;
- observability schema/helper/hooks compile;
- live branch remains `carrot-wip`.

### Gate C — equivalence
- observer OFF vs ON control-relevant outputs identical on deterministic fixtures;
- observer forced-failure outputs identical;
- replay trace contains required H1 identities.

### Gate D — simulator integration
- Carrot-comma-SIM can ingest the retained H1 schema;
- unsupported/missing schema is explicit HOLD/fail-closed for replay evidence, not silently guessed;
- H0/H1 tests pass.

### Gate E — device verification
- offroad boot succeeds;
- normal Carrot services run;
- logging appears in route data;
- no new process crash/manager instability attributable to observer;
- only then resume normal road data collection.

## 10. Branch cleanup policy

Do not immediately delete historical branches. First mark eGPU/integrated branches as research/archive candidates and stop using them as mainline. After the clean live `carrot-wip` observability overlay and simulator adapter pass Gates A-E, delete only branches confirmed to contain no unique required H1/simulator evidence.

## 11. Success criteria

The restructuring is complete when:
- the comma remains on normal `carrot-wip` and can keep following upstream;
- the only live non-upstream differences are the documented minimal observability overlay;
- eGPU has zero runtime/build dependency for the simulator path;
- H1 replay has the missing loop/config/radar evidence it needs;
- Carrot-comma-SIM remains the single project mainline for H0/H1/H2 and closed-loop work;
- observer failure cannot alter live driving control behavior.
