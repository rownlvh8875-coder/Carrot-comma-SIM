# Carrot-comma-SIM

> **A multi-vehicle closed-loop simulator research project for testing Carrot/openpilot-family controllers without repeatedly driving the real vehicle.**  
> The first reference vehicle is `HYUNDAI_SANTA_FE_2022`.

[한국어](README.md) · [English](README_EN.md)

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
| Real-road observability research | in progress |
| Automatic parameter tuning | not authorized |
| Real-vehicle writes | disabled / not part of this public core |

This is a **sanitized public research release**. Private raw driving logs, route identifiers, device/network identifiers, SSH information, personal paths, and sensitive provenance records are intentionally excluded.

## H0 / H1 / H2

The project separates evidence into stages instead of tuning first and explaining later.

- **H0 — data identity/provenance:** prove which vehicle, code and configuration produced the evidence.
- **H1 — controller replay fidelity:** check whether the historical controller output can be reproduced from the corresponding inputs.
- **H2 — vehicle-response identification:** model how the real vehicle responds to controller commands.

```text
H0 → H1 → H2 → closed-loop simulation → synthetic stress/scenario testing
```

## Research and safety principles

The public contracts intentionally enforce conservative behavior:

1. An external world simulator may not silently replace a calibrated vehicle plant.
2. Inputs outside the declared validated domain fail closed by default.
3. Synthetic scenarios do not become real-road acceptance evidence.
4. One-step fitting is not declared closed-loop validation.
5. Scenario scores and descriptive metrics do not create tuning authority.
6. This public simulator core does not write values to a real vehicle.

> This project is a research/simulation tool. It does not certify real-road safety and does not replace driver responsibility.

## Quick start

Python 3.11+ is recommended.

```bash
git clone https://github.com/rownlvh8875-coder/Carrot-comma-SIM.git
cd Carrot-comma-SIM
python -m unittest discover -s tests -p 'test_*.py' -v
python examples/basic_closed_loop.py
```

The initial public core has no third-party Python runtime dependencies.

## Repository layout

```text
carrot_sim/
  simulator_contract.py
  vehicle_plant_axes.py
  simulator_loop.py
  scenario_test_catalog.py
examples/
  basic_closed_loop.py
tests/
docs/
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

The redistribution license for this repository's own code has not yet been selected. Public GitHub visibility by itself does not grant additional reuse rights.
