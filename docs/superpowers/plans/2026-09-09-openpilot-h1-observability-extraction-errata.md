# H1 Observability Extraction Plan — Corrections

Date: 2026-09-09

This file corrects two assumptions in `2026-09-09-openpilot-h1-observability-extraction.md`. These corrections are authoritative for implementation.

## 1. Carrot plannerd hook

The plan text referred to `def plannerd_thread`. That is not the Carrot-WIP structure used by this project.

Verified source:
- historical live base `ce3d76301c988db8aa955e1ebc6496f0a0fd2abc`: `openpilot/selfdrive/controls/plannerd.py` uses `def main()`;
- reviewed upstream on 2026-09-09 `dcce955ce4926cc012d0eae8d57a82e42555131a`: the same file uses `def main()`.

Therefore the H1 host-surface compatibility anchor is `def main():`.

## 2. Native upstream eGPU code is not an incompatibility

The plan proposed treating eGPU-named files found anywhere in the upstream checkout as forbidden. That would incorrectly make upstream-owned Carrot features part of this simulator project's scope.

Correct rule:
- this project must not add an eGPU dependency to the H1 observability overlay or simulator H0/H1/H2 path;
- native upstream Carrot code may contain eGPU-related functionality and is not rejected merely by name;
- compatibility inspection is limited to the small H1 host surface: cereal reserved slots, service registry, `CarrotPlanner`, `LongitudinalPlanner`, and Carrot `plannerd.py` `main()`.

## 3. Schema-v6 evidence completeness

Implementation review established that historical `CarrotH1ReplayTrace` schema-v6 contains 54 fields. Simulator ingestion therefore requires the complete schema-v6 trace, not a reduced subset, and recomputes `consumedSnapshotIdentitySha256` using the historical canonical-JSON algorithm before an evidence record can participate in `H1_READY` qualification.
