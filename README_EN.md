# Carrot-comma-SIM

> **A multi-vehicle closed-loop simulator research project for testing Carrot/openpilot-family controllers without repeatedly driving the real vehicle.**  
> The first reference vehicle is `HYUNDAI_SANTA_FE_2022`.

[한국어](README.md) · [English](README_EN.md) · [Current project status (KO)](docs/PROJECT_STATUS_KO.md) · [Output flow (KO)](docs/HOW_SIMULATION_OUTPUT_WORKS_KO.md) · [Scoring & tuning contract (KO)](docs/SCORING_AND_TUNING_KO.md) · [Public/private policy (KO)](docs/PUBLIC_PRIVATE_REPO_POLICY_KO.md)

## What this project is

The long-term goal is to separate the real controller from a validated vehicle-response model and run the following loop on a computer:

```text
Carrot / openpilot Controller
            ↓
       PlantControl
            ↓
   CombinedVehiclePlant
      ├─ Lateral Plant
      └─ Longitudinal Plant
            ↓
        VehicleState
            ↓
        WorldBackend
   road / lead / traffic / sensors
            ↓
      back to Controller
```

The controller output changes the simulated vehicle state, and that new state becomes the next controller input. This is the closed loop.

### What does a simulation run produce?

```text
vehicle + Carrot settings + scenario
        → controller command
        → vehicle-plant response
        → time-series vehicle state
        → safety-related / comfort / tracking metrics
        → baseline-versus-candidate comparison
```

A hard-braking lead scenario, for example, should show the deceleration Carrot requested, the delayed/dynamic vehicle response, and the resulting minimum gap, TTC, jerk and tracking error. The intended output includes raw metrics, plots, worst-case scenarios and trade-offs rather than a single opaque score. See [`docs/HOW_SIMULATION_OUTPUT_WORKS_KO.md`](docs/HOW_SIMULATION_OUTPUT_WORKS_KO.md); its numbers are illustrative, not validated vehicle measurements.

## Multi-vehicle architecture

The project started with a 2022 Hyundai Santa Fe, but the common simulator core is intentionally vehicle-independent.

```text
CombinedVehiclePlant
        │
        ├─ CombinedSantaFePlant   # first reference vehicle
        ├─ FutureVehicleBPlant
        └─ FutureVehicleCPlant
```

A new vehicle should bring its own evidence-bound lateral and longitudinal response models plus a declared validated operating domain. The world/scenario framework should remain reusable.

## Current public status

| Area | Status |
|---|---|
| World / Vehicle Plant separation | implemented |
| Generic `CombinedVehiclePlant` | implemented |
| Santa Fe strict reference wrapper | implemented |
| Lateral reference model | frozen baseline exists in the research project |
| Longitudinal plant | research in progress |
| Deterministic scenario catalog | implemented |
| H1 evidence structural validation | implemented: complete schema-v6 trace, config SHA, snapshot identity, and trigger/radar semantics |
| Real comma inventory / H1 overlay offroad qualification | completed: backup, latest upstream synchronization, minimal overlay reapply, build/reboot/runtime-schema checks |
| Real H1 controller replay fidelity | pending a new moving schema-v6 route |
| Parameter candidate scoring/recommendation | contract documented; no automatic real-vehicle parameter write |
| Real-vehicle writes | disabled / not part of this public core |

`H1_READY` means the evidence is structurally sufficient to begin deterministic controller-replay research. It does **not** mean controller outputs have already been reproduced, that the vehicle plant is validated, or that real-road safety has been established. See [`docs/H1_OBSERVABILITY_KO.md`](docs/H1_OBSERVABILITY_KO.md) for the current evidence contract.

### Immediate next step

The real comma inventory, recoverable backup, latest `carrot-wip` synchronization, minimal H1 observability overlay reapply, offroad build, reboot, and runtime schema checks are complete. Device identifiers, network details, and personal paths remain private.

The next empirical gate is a **vehicle-connected moving schema-v6 route**:

```text
connect the vehicle and confirm stationary state
        ↓
confirm CarParams / fingerprint / real plannerd startup
        ↓
confirm carrotH1ReplayTrace + carrotH1ConfigSnapshot activity
        ↓
capture a short moving route
        ↓
validate trace/config continuity and provenance
        ↓
validate controller output replay fidelity
```

There is no reason to perform repeated unconditional pulls on the live comma at this point. Future upstream changes should first be classified for simulator/observer compatibility while preserving the minimal H1 overlay.

This is a **sanitized public research release**. Private raw driving logs, route identifiers, device/network identifiers, SSH information, personal paths, and sensitive provenance records are intentionally excluded.

## H0 / H1 / H2

The project separates evidence into stages instead of tuning first and explaining later.

- **H0 — data identity/provenance:** prove which vehicle, code and configuration produced the evidence.
- **H1 — controller replay fidelity:** check whether the historical controller output can be reproduced from the corresponding inputs. The public core now validates whether normalized schema-v6 H1 evidence is structurally complete and internally consistent; actual replay fidelity remains a separate real-evidence step.
- **H2 — vehicle-response identification:** model how the real vehicle responds to controller commands.

```text
H0 → H1 → H2 → closed-loop simulation → synthetic stress/scenario testing
```

## H1 observability boundary

Normal `rlog`/`qlog` remain primary route evidence. The minimal H1 overlay exists only to preserve planner-consumed state that can otherwise be ambiguous during deterministic replay, including loop timing, the exact planning trigger, nine service receive identities, consumed configuration identity, and effective radar identity.

The public parser requires the complete historical schema-v6 `carrotH1ReplayTrace` contract and verifies its historical `consumedSnapshotIdentitySha256` by recomputing the same canonical-JSON SHA256. It also verifies the canonical config payload hash and trigger/radar/run semantics. Missing or inconsistent evidence is never silently guessed.

The live overlay is limited to observation-only schema/service/helper/hooks required for H1 replay evidence. It must not maintain eGPU/Guardian/model-slot/telemetry, steering/braking/acceleration policy changes, Panda safety changes, actuator-limit changes, or a separate simulator-owned Carrot control fork.

Normalized JSONL can be checked with:

```bash
python scripts/inspect_h1_evidence.py examples/h1_evidence_ready.jsonl
python scripts/inspect_h1_evidence.py examples/h1_evidence_missing_config.jsonl
```

Exit codes are `0 = H1_READY`, `2 = H1_HOLD`, and `3 = H1_ERROR`.

The Carrot/openpilot host surface for the minimal overlay can be inspected read-only with:

```bash
python scripts/check_openpilot_overlay.py /path/to/openpilot
```

This compatibility result describes only the maintenance status of the instrumentation overlay. It is not a safety approval of an upstream Carrot release.

## Research and safety principles

The public contracts intentionally enforce conservative behavior:

1. An external world simulator may not silently replace a calibrated vehicle plant.
2. Inputs outside the declared validated domain fail closed by default.
3. Synthetic scenarios do not become real-road acceptance evidence.
4. One-step fitting is not declared closed-loop validation.
5. Scenario scores and descriptive metrics do not create tuning authority.
6. This public simulator core does not write values to a real vehicle.
7. Missing, malformed, or inconsistent H1 evidence is held or rejected rather than reconstructed by guesswork.

> This project is a research/simulation tool. It does not certify real-road safety and does not replace driver responsibility.

## Quick start

Python 3.11+ is recommended.

```bash
git clone https://github.com/rownlvh8875-coder/Carrot-comma-SIM.git
cd Carrot-comma-SIM
python -m unittest discover -s tests -p 'test_*.py' -v
python examples/basic_closed_loop.py
```

The public core has no third-party Python runtime dependencies.

## Repository layout

```text
carrot_sim/
  h1_evidence.py
  h1_evidence_set.py
  h1_jsonl.py
  openpilot_overlay_compat.py
  simulator_contract.py
  vehicle_plant_axes.py
  simulator_loop.py
  scenario_test_catalog.py
examples/
  basic_closed_loop.py
  h1_evidence_ready.jsonl
  h1_evidence_missing_config.jsonl
integration/openpilot/
  h1_overlay_manifest.json
scripts/
  inspect_h1_evidence.py
  check_openpilot_overlay.py
tests/
docs/
  PROJECT_STATUS_KO.md
  H1_OBSERVABILITY_KO.md
  ARCHITECTURE_KO.md
  VEHICLE_PLUGIN_GUIDE_KO.md
```

## Adding another vehicle

A vehicle is not considered supported merely because a class name exists. The intended workflow is:

```text
new vehicle logs
  ↓
provenance / configuration checks
  ↓
lateral response identification
  ↓
longitudinal response identification
  ↓
validated domain declaration
  ↓
independent validation data
  ↓
vehicle plugin registration
  ↓
shared closed-loop + scenario engine
```

## Roadmap

- [x] World / Vehicle Plant separation
- [x] Generic `CombinedVehiclePlant`
- [x] Santa Fe strict reference wrapper
- [x] Fail-closed simulator contract
- [x] Deterministic scenario catalog
- [x] Strict schema-v6 H1 evidence parsing / structural qualification
- [x] Remove eGPU/integrated branches from the simulator's required path
- [x] Real comma read-only inventory / H1 overlay classification / latest-upstream offroad qualification
- [ ] Capture a moving real-comma H1 route and validate controller replay fidelity
- [ ] Complete Santa Fe longitudinal plant validation
- [ ] Publish a sanitized real Carrot/openpilot controller bridge
- [ ] Freeze a standard Vehicle Profile / Plugin format
- [ ] Validate the workflow on a second vehicle
- [ ] Expand world adapters (MetaDrive/SUMO/CommonRoad family)
- [ ] Automated regression and scenario-coverage reporting

## Privacy policy for the public repository

The repository intentionally excludes raw `rlog`/`qlog`, route IDs, comma hostnames/IP addresses, SSH material, personal filesystem paths, device identifiers, and source metadata that could reveal a private driving route. Only synthetic examples and safely anonymized summaries should be published.

## Relationship to Carrot / openpilot

This is an independent simulator research project intended to work with Carrot/openpilot-family controllers. The public repository does not vendor the full openpilot or Carrot source tree. Upstream names, trademarks, code and licenses remain with their respective projects.

Normal Carrot-WIP updates are not approved or blocked by this simulator project. We maintain only the minimal observability overlay required for replay evidence and its compatibility boundary. Historical eGPU/Guardian/model-slot/telemetry/commissioning research is not a required dependency of the simulator H0/H1/H2 path.

The redistribution license for this repository's own code has not yet been selected. Public GitHub visibility by itself does not grant additional reuse rights.
