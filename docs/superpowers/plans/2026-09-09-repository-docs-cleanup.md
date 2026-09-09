# Repository Documentation Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `main` documentation reflect the current simulator/H1 state and remove superseded internal implementation-plan artifacts without deleting unique project evidence.

**Architecture:** Keep README and stable `docs/*.md` as the public source of truth. Preserve implementation decisions in `docs/H1_OBSERVABILITY_KO.md` and a concise current-status document, then remove `docs/superpowers/plans/*` and `docs/superpowers/specs/*` because they are process artifacts rather than runtime/project documentation.

**Tech Stack:** Markdown, GitHub, Python CI already configured in the repository.

**Spec:** Current `main` README/H1 architecture plus the approved project boundary captured in the superseded spec before deletion.

## Global Constraints

- `Carrot-comma-SIM` remains the simulator project mainline.
- `ajouatom/openpilot:carrot-wip` remains authoritative live control software.
- eGPU/Guardian/model-slot/telemetry are not dependencies of the simulator H0/H1/H2 path.
- Real comma changes are not performed by this repository-cleanup task.
- Do not delete code, tests, examples, H1 manifest, or stable architecture/plugin/H1 documentation.
- Do not claim actual H1 replay fidelity until real comma H1 evidence is collected and replayed.

---

### Task 1: Publish a current project status source of truth

**Files:**
- Create: `docs/PROJECT_STATUS_KO.md`
- Modify: `README.md`
- Modify: `README_EN.md`

**Interfaces:**
- Consumes: current `main`, merged PR #3 state, H1 structural validator state.
- Produces: user-facing current status and exact next-step boundary.

- [ ] Create a concise status document separating completed, waiting-for-device, and later-road-validation work.
- [ ] Link it from Korean and English READMEs.
- [ ] State that the next device step starts with read-only `/data/openpilot` inventory before pull/reset/reapply.

### Task 2: Consolidate durable H1/live-overlay rules

**Files:**
- Modify: `docs/H1_OBSERVABILITY_KO.md`
- Modify: `docs/ARCHITECTURE_KO.md`

**Interfaces:**
- Consumes: durable rules currently present in the superseded boundary spec.
- Produces: stable documentation that remains valid after internal plans are removed.

- [ ] Add explicit allowed/forbidden live overlay boundaries to H1 documentation.
- [ ] Add repository-responsibility boundary to architecture documentation.
- [ ] Keep eGPU mentioned only as an explicit non-dependency/excluded research topic, not as a simulator component.

### Task 3: Remove superseded internal planning artifacts

**Files:**
- Delete: `docs/superpowers/plans/2026-09-09-openpilot-h1-observability-extraction-errata.md`
- Delete: `docs/superpowers/plans/2026-09-09-openpilot-h1-observability-extraction.md`
- Delete: `docs/superpowers/plans/2026-09-09-simulator-h1-evidence-ingestion.md`
- Delete: `docs/superpowers/specs/2026-09-09-carrot-observability-simulator-boundary-design.md`
- Delete this cleanup plan before merge.

**Interfaces:**
- Consumes: completed consolidation from Tasks 1-2.
- Produces: a repository with no stale agent/process plans presented as current documentation.

- [ ] Verify no stable README/doc links depend on these files.
- [ ] Delete only the superseded plan/spec artifacts.

### Task 4: Verify and integrate

**Files:**
- No new runtime files.

**Interfaces:**
- Consumes: cleaned feature branch.
- Produces: verified `main` documentation cleanup.

- [ ] Run existing CI unchanged.
- [ ] Confirm public privacy audit remains PASS.
- [ ] Review changed filenames to ensure no runtime/control files changed.
- [ ] Squash merge after green CI.
