# Carrot-comma-SIM 현재 상태

기준일: 2026-09-10

> 문서 역할과 최신/구조 문서 구분은 [`DOCUMENT_STATUS_KO.md`](DOCUMENT_STATUS_KO.md)를 먼저 참고합니다.

## 1. 프로젝트 목적

`Carrot-comma-SIM`은 Carrot/openpilot 계열 제어기를 실제 차량 없이 반복 재생·검증하고, 차량 반응 모델과 결합해 폐루프 시뮬레이션까지 확장하기 위한 독립 시뮬레이터 프로젝트입니다.

실차 주행 소프트웨어 자체를 별도 포크 제품으로 유지하는 것이 목적이 아닙니다. 실차의 authoritative control source는 `ajouatom/openpilot:carrot-wip`이며, 이 저장소는 그 제어 결과를 재현·분석·회귀검증하는 쪽을 담당합니다.

### Reference Vehicle identity 주의

공개 문서의 `HYUNDAI_SANTA_FE_2022`는 openpilot/시뮬레이터에서 사용하는 **software reference identity**입니다. 이 식별자만으로 비공개 실제 시험차의 등록연식·세부 트림을 추정하지 않습니다. 실제 차량 identity와 현재 `CarParams`/fingerprint는 private H0 evidence에서 별도로 관리·검증합니다.

## 2. 현재 완료된 범위

- World / Vehicle Plant / Controller 경계 분리
- 범용 `CombinedVehiclePlant`
- Santa Fe strict reference wrapper
- fail-closed simulation contract
- 결정론적 scenario catalog 및 회귀 테스트
- H1 schema-v6 전체 54-field trace parser
- canonical config SHA256 검증
- historical `consumedSnapshotIdentitySha256` 재계산 검증
- trigger/radar/run 의미 일관성 검증
- `H1_READY` / `H1_HOLD` / `H1_ERROR` 판정
- normalized H1 JSONL ingestion 및 CLI
- openpilot H1 host-surface 읽기 전용 compatibility checker
- eGPU/Guardian/model-slot/telemetry를 simulator H0/H1/H2 필수 경로에서 분리
- 공개 개인정보 audit 및 Python 3.11/3.12 CI
- Safety-related performance / Comfort / Tracking 평가·추천 계약 문서화
- 공개 core와 private evidence/tuning layer 운영정책 문서화
- 차량세팅 입력부터 Controller/Vehicle Plant/시간축 결과/후보 비교까지의 쉬운 설명자료 문서화
- README / architecture / H1 / current-status 문서 최신화
- 완료된 `docs/superpowers` plan/spec 제거
- 병합 완료 작업 브랜치 `codex/selective-public-20260907`, `feat/h1-evidence-v1` 제거
- 실제 comma read-only inventory 및 기존 H1 observability 변경 분류 완료
- 최신 `carrot-wip` 기준 최소 H1 overlay 재적용 및 offroad build/reboot/runtime schema 검증 완료
- stage H1 관련 회귀검증 `196/196 PASS`, capture/publish fail-open 경로 포함
- live comma에서 `carrotH1ReplayTrace` / `carrotH1ConfigSnapshot` runtime schema 생성 확인

## 3. 아직 완료되지 않은 범위

현재 `H1_READY`는 evidence 구조와 무결성이 controller replay를 시작할 만큼 충분하다는 뜻입니다. Private real-world evidence에서는 새 moving schema-v6 bounded window의 controller output replay 일치까지 확인됐습니다. 아직 남은 실증은 **prospective robust H1 acceptance**입니다.

- development A route exact replay
- development B route exact replay
- 두 development PASS 후 별도 승인된 sealed holdout 1회 replay
- Santa Fe longitudinal Vehicle Plant의 최종 검증
- 실제 Carrot/openpilot controller bridge의 공개판 정리
- 차량별 표준 Vehicle Profile / Plugin 포맷 확정
- 두 번째 차량에서 전체 방법론 재현

## 4. 다음 작업 — robust H1 acceptance

실제 comma의 read-only inventory/offroad 검증과 private bounded moving H1 replay proof까지 완료했습니다. 다음 단계는 결과 확인 전에 역할을 고정한 **development A / development B / sealed holdout** 검증입니다.

현재 일반화된 상태:

```text
upstream carrot-wip 최신 기준선 = 동기화 완료
최소 H1 observability overlay   = 유지
offroad build / reboot          = PASS
runtime H1 schema               = PASS
실차 moving H1 evidence         = bounded proof 확보
controller replay fidelity      = bounded PASS / robust acceptance pending
real vehicle write              = false
```

다음 순서:

```text
bounded moving replay proof
  ↓
prospective robust H1 contract
  ↓
development A exact replay
  ↓
development B exact replay
  ↓
개발 2개 PASS 후 sealed holdout 별도 1회 검증
  ↓
robust H1 PASS
  ↓
별도 H2 evidence qualification review
  ↓
H2가 승인된 뒤에만 longitudinal Plant 식별/검증
```

upstream이 다시 바뀌기 전까지 live comma에서 반복적인 무조건 `git pull`은 필요하지 않습니다. 이후 업데이트는 H1 overlay 보존과 compatibility 확인을 전제로 처리합니다.

## 5. 저장소 책임 경계

### `ajouatom/openpilot:carrot-wip`

- 실차 주행 소프트웨어
- upstream이 제어 기능과 주행 정책을 관리
- 이 시뮬레이터가 일반 upstream 업데이트를 승인/차단하지 않음

### live comma `/data/openpilot`

- 정상 `carrot-wip` 사용
- 일반 로그로 부족한 H1 replay evidence만 최소 observability overlay로 보완
- steering/braking/acceleration policy, Panda safety, actuator limit를 simulator 프로젝트가 변경하지 않음

### `Carrot-comma-SIM`

- H0 provenance
- H1 replay evidence 검증 및 controller replay
- H2 Vehicle Plant 식별/검증
- closed-loop simulation
- deterministic scenario regression
- upstream 변경에 대한 simulator/observability compatibility 검사

## 6. eGPU 관련 정리

eGPU는 과거 참고·연구 대상으로 분석된 이력이 있으나 현재 시뮬레이터의 필수 구성요소가 아닙니다.

- simulator runtime dependency: 없음
- H0/H1/H2 acceptance dependency: 없음
- live comma update prerequisite: 아님
- 향후 별도 eGPU 연구가 명시적으로 필요해질 때만 독립 주제로 다룸

## 7. 현재 브랜치 정리 상태

현재 유지 브랜치는 두 개입니다.

- `main` — 현재 프로젝트 기준선
- `review/followup-hardening` — PR #1의 미검증 hardening 후보 보존용

`review/followup-hardening`은 `main`에 없는 고유 커밋이 남아 있고, plant/snapshot/duration 및 release-audit 관련 변경이 아직 별도 offline compatibility/revalidation을 필요로 하므로 삭제하지 않습니다.

반대로 아래 두 브랜치는 정리 완료했습니다.

- `codex/selective-public-20260907` — PR #2 merge 완료, 고유 미반영 커밋 없음
- `feat/h1-evidence-v1` — PR #3 squash merge 완료, 최종 기능 트리가 `main`에 반영됨

## 8. 현재 기준 문서

프로젝트 상태를 판단할 때는 다음 순서로 문서를 봅니다.

1. [`docs/DOCUMENT_STATUS_KO.md`](DOCUMENT_STATUS_KO.md) — 문서 역할·최신성 인덱스
2. [`README.md`](../README.md) — 전체 프로젝트 개요와 로드맵
3. [`docs/PROJECT_STATUS_KO.md`](PROJECT_STATUS_KO.md) — 현재 완료/미완료/다음 작업
4. [`docs/HOW_SIMULATION_OUTPUT_WORKS_KO.md`](HOW_SIMULATION_OUTPUT_WORKS_KO.md) — 차량세팅 입력부터 결과/비교까지의 쉬운 설명
5. [`docs/ARCHITECTURE_KO.md`](ARCHITECTURE_KO.md) — 구조와 책임 경계
6. [`docs/H1_OBSERVABILITY_KO.md`](H1_OBSERVABILITY_KO.md) — H1 evidence 계약과 실차 observability 원칙
7. [`docs/SCORING_AND_TUNING_KO.md`](SCORING_AND_TUNING_KO.md) — 안전 관련 성능·승차감·추종성 및 파라미터 추천 기준
8. [`docs/PUBLIC_PRIVATE_REPO_POLICY_KO.md`](PUBLIC_PRIVATE_REPO_POLICY_KO.md) — 공개 core / 비공개 evidence·튜닝 계층 운영정책
9. [`docs/VEHICLE_PLUGIN_GUIDE_KO.md`](VEHICLE_PLUGIN_GUIDE_KO.md) — 차량 확장 규칙

구현이 끝난 과거 작업계획·agent용 plan/spec 문서는 제거했으며 현재 프로젝트 상태의 source of truth로 사용하지 않습니다.
