# Carrot-comma-SIM 현재 상태

기준일: 2026-09-09

## 1. 프로젝트 목적

`Carrot-comma-SIM`은 Carrot/openpilot 계열 제어기를 실제 차량 없이 반복 재생·검증하고, 차량 반응 모델과 결합해 폐루프 시뮬레이션까지 확장하기 위한 독립 시뮬레이터 프로젝트입니다.

실차 주행 소프트웨어 자체를 별도 포크 제품으로 유지하는 것이 목적이 아닙니다. 실차의 authoritative control source는 `ajouatom/openpilot:carrot-wip`이며, 이 저장소는 그 제어 결과를 재현·분석·회귀검증하는 쪽을 담당합니다.

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

## 3. 아직 완료되지 않은 범위

현재 `H1_READY`는 evidence 구조와 무결성이 controller replay를 시작할 만큼 충분하다는 뜻입니다. 다음 항목은 아직 실증 완료가 아닙니다.

- 실제 comma에서 새 H1 observability evidence 확보
- 실제 route 기반 controller output equality / replay fidelity 검증
- Santa Fe longitudinal Vehicle Plant의 최종 검증
- 실제 Carrot/openpilot controller bridge의 공개판 정리
- 차량별 표준 Vehicle Profile / Plugin 포맷 확정
- 두 번째 차량에서 전체 방법론 재현

## 4. 다음 작업 — 실제 comma 연결 후

다음 단계는 코드 작성이 아니라 먼저 **현재 comma 상태를 읽기 전용으로 확정**하는 것입니다.

순서:

```text
comma 연결
  ↓
/data/openpilot branch / HEAD / remotes 확인
  ↓
git status --short 및 local diff 확보
  ↓
H1 관련 기존 변경만 별도 분류
  ↓
OBSERVABILITY_REQUIRED / SIMULATOR_OFFLINE / UNRELATED / REMOVE
  ↓
백업이 확보된 뒤에만 최신 carrot-wip 동기화 검토
  ↓
최소 H1 observability overlay 재적용/유지
  ↓
offroad 기동 및 logging 확인
  ↓
새 실주행 evidence 확보
```

초기 점검이 끝나기 전에는 `reset --hard`, 무조건적인 `git pull`, 기존 H1 파일 삭제를 하지 않습니다.

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

## 7. 현재 기준 문서

프로젝트 상태를 판단할 때는 다음 순서로 문서를 봅니다.

1. `README.md` — 전체 프로젝트 개요와 로드맵
2. `docs/PROJECT_STATUS_KO.md` — 현재 완료/미완료/다음 작업
3. `docs/ARCHITECTURE_KO.md` — 구조와 책임 경계
4. `docs/H1_OBSERVABILITY_KO.md` — H1 evidence 계약과 실차 observability 원칙
5. `docs/VEHICLE_PLUGIN_GUIDE_KO.md` — 차량 확장 규칙

구현이 끝난 과거 작업계획·agent용 plan/spec 문서는 현재 프로젝트 상태의 source of truth로 사용하지 않습니다.
