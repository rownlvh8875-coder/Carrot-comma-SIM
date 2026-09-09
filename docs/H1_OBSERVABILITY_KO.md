# H1 Observability — 제어기 재현을 위한 최소 관측 증거

기준일: 2026-09-09

## 1. 목적

Carrot-comma-SIM의 H1 단계는 **과거 주행 당시 Carrot/openpilot 제어기가 실제로 소비한 입력과 설정을 다시 구성해 같은 제어 결과를 재현할 수 있는지** 확인하는 단계입니다.

일반 `rlog`/`qlog`는 계속 가장 중요한 주행 기록입니다. 다만 비동기 메시지 수신 시점, planner loop trigger, loop 사이에 실제로 소비된 Params/config, fast radar overlay 적용 여부처럼 **나중에 주변 로그만 보고 정확히 복원하기 어려운 경계**가 있습니다.

H1 observability는 이 누락을 보완하기 위한 최소 계측입니다. 제어 정책을 바꾸기 위한 기능이 아닙니다.

## 2. 실차와 시뮬레이터의 책임 분리

```text
Carrot-WIP on comma
  ├─ 기존 rlog / qlog
  └─ 최소 H1 observability
          ↓
    private evidence export
          ↓
Carrot-comma-SIM
  H0 provenance
          ↓
  H1 evidence validation / controller replay
          ↓
  H2 vehicle plant
          ↓
  closed-loop simulation
```

- 실차의 주행 결정은 Carrot-WIP가 계속 담당합니다.
- Carrot-comma-SIM은 실차 제어값이나 Params를 쓰지 않습니다.
- eGPU/Guardian/model-slot/telemetry/shadow commissioning은 H1 필수 경로가 아닙니다.

### live comma에 허용되는 최소 변경

- H1 replay trace/config snapshot 메시지 정의와 service 등록
- 작은 `H1Observability` helper
- planner가 실제 소비한 입력/config/trigger를 기록하기 위한 최소 hook
- replay decode에 실제로 필요할 때만 Hyundai radar DBC 보완
- observability ON/OFF 및 강제 실패 시 control-relevant output이 동일함을 검증하는 테스트/진단

### live comma에서 이 프로젝트가 유지하지 않는 변경

- eGPU integration, BIG/SMALL model commissioning, Guardian, eGPU telemetry, model-slot activation, shadow runner
- steering/braking/acceleration policy 변경
- Panda safety 또는 actuator limit 변경
- 별도의 Carrot 제어 알고리즘 포크
- simulator 편의를 위해 실차 주행 결정을 바꾸는 코드

관측 코드의 실패는 **fail-open for driving**이어야 합니다. 즉 trace/config 직렬화·publish 실패가 제어 루프의 판단, steering, braking, acceleration authority를 바꾸거나 프로세스를 종료시키면 안 됩니다.

## 3. 현재 H1 스키마

현재 지원하는 H1 observability schema version은 **6**입니다.

두 종류의 기록을 사용합니다.

### `carrotH1ReplayTrace`

historical schema-v6의 **54개 필드를 모두 요구**합니다. planner main-loop 단위로 다음 재현 경계를 보존합니다.

- `processEpoch`, `loopSequence`, `plannerCycle`, `subMasterFrame`
- `captureMonoTimeNs`, `decisionMonoTimeNs`
- `planningTriggerKind`, `planningTriggerLogMonoTime`
- 9개 service(`modelV2`, `liveTracks`, `carControl`, `carState`, `controlsState`, `liveParameters`, `radarState`, `selfdriveState`, `carrotMan`) 각각의 `logMonoTime`, `recvFrame`, `recvTimeNs`
- `seenMask`, `updatedMask`, `aliveMask`, `freqOkMask`, `validMask`
- `configSequence`, `configSha256`
- `radarInputKind`, `fastLeadMask`, `fastLeadTrackId`, `fastLeadReason`, `effectiveRadarStateSha256`
- `runLongitudinal`, `longitudinalPlanEmitted`, `liveTracksRecent`, `useLiveTracksTrigger`, `triggerIntervalOk`
- `consumedSnapshotIdentitySha256`

시뮬레이터는 `consumedSnapshotIdentitySha256`를 그대로 신뢰하지 않습니다. historical `h1_observability.py`와 동일하게 위 loop identity payload를 canonical JSON으로 직렬화하고 SHA256을 다시 계산해 기록값과 정확히 비교합니다.

또한 historical `plannerd.py`의 실제 생성 규칙과 다음 의미 일관성을 검사합니다.

- `useLiveTracksTrigger=false`이면 planning trigger는 `modelV2`, `true`이면 `liveTracks`
- `planningTriggerLogMonoTime`은 선택된 trigger service의 실제 `logMonoTime`과 같아야 함
- `runLongitudinal=true`이면 `triggerIntervalOk=true`
- `longitudinalPlanEmitted=true`이면 `runLongitudinal=true`
- emitted cycle의 `radarInputKind`는 trigger 경로와 일치해야 함
- non-emitted cycle은 `radarInputKind=2`이고 effective radar SHA가 비어 있어야 함

### `carrotH1ConfigSnapshot`

제어기가 실제 소비한 설정 조합이 바뀔 때 canonical JSON과 SHA256 identity를 기록합니다.

시뮬레이터는 canonical JSON 바이트를 다시 SHA256하여 기록된 `configSha256`과 정확히 일치하는지 검사합니다. JSON의 의미가 같더라도 canonical byte representation이 다르면 동일 증거로 간주하지 않습니다.

## 4. `H1_READY`의 의미

`H1_READY`는 다음을 뜻합니다.

> 해당 evidence set이 **결정론적 controller replay 연구를 시작하기에 구조적으로 충분하다**.

현재 검사 항목에는 다음이 포함됩니다.

- schema version 6 및 54-field trace completeness
- historical snapshot identity SHA256 재계산 일치
- trigger/radar/run 의미 일관성
- loop sequence 연속성
- 동일 process epoch
- planner cycle 전이 일관성
- emitted cycle의 config/radar identity 존재
- config snapshot sequence/SHA 연결
- config sequence collision 여부
- canonical config payload SHA256 검증

`H1_READY`는 다음을 의미하지 않습니다.

- Carrot 제어기가 안전하다는 보증
- 실도로 안전성 검증 완료
- H1 replay 출력이 이미 실제 기록과 완전히 일치한다는 뜻
- H2 차량 Plant가 검증되었다는 뜻
- 자동 파라미터 튜닝 권한

실제 controller output replay 비교는 `H1_READY` 이후 별도 검증 단계입니다.

## 5. `H1_HOLD`의 의미

증거가 부족하거나 evidence set 간 연결이 불확실하면 값을 추측하지 않고 `H1_HOLD`로 둡니다.

예시 HOLD 사유:

- `NO_H1_TRACE`
- `MIXED_PROCESS_EPOCH`
- `LOOP_SEQUENCE_GAP`
- `PLANNER_CYCLE_INVALID`
- `MISSING_EFFECTIVE_IDENTITY`
- `MISSING_CONFIG_SNAPSHOT`
- `CONFIG_IDENTITY_MISMATCH`
- `CONFIG_SEQUENCE_COLLISION`

중요한 점은 **raw rlog/qlog가 있다고 해서 자동으로 H1_READY로 승격하지 않는 것**입니다. 기존 로그만으로도 H0, H2 또는 일부 replay 분석은 가능할 수 있지만, planner가 특정 loop에서 무엇을 실제로 소비했는지를 확정할 수 없으면 deterministic H1 증거로는 HOLD합니다.

## 6. `H1_ERROR`

다음과 같이 개별 evidence 자체가 계약을 위반하면 구조적 HOLD와 구분해 `H1_ERROR`로 처리합니다.

- malformed JSON
- 지원하지 않는 schema version
- schema-v6 필수 필드 누락 또는 정수 범위 위반
- 잘못된 SHA256 형식
- `consumedSnapshotIdentitySha256` 재계산 불일치
- planning trigger kind/timestamp 불일치
- emitted/non-emitted radar/run 의미 불일치
- config payload/hash 불일치
- non-canonical config JSON
- 알 수 없는 record type

CLI exit code:

```text
0 = H1_READY
2 = H1_HOLD
3 = H1_ERROR
```

검사 예:

```bash
python scripts/inspect_h1_evidence.py examples/h1_evidence_ready.jsonl
```

## 7. normalized JSONL 경계

공개 시뮬레이터는 openpilot Cap'n Proto runtime을 직접 의존하지 않습니다. 실제 route에서 추출한 H1 메시지는 아래 envelope로 정규화합니다.

```json
{"type":"carrotH1ReplayTrace","data":{}}
```

또는

```json
{"type":"carrotH1ConfigSnapshot","data":{}}
```

실제 원본 route, dongle ID, IP, 개인 경로, 영상 등은 공개 저장소에 커밋하지 않습니다.

## 8. Carrot 업데이트와의 관계

Carrot-WIP 업데이트 자체를 이 프로젝트가 승인하거나 차단하지 않습니다.

우리가 유지하는 것은 **작은 observability overlay의 호환성**입니다.

현재 compatibility gate는 다음 host surface만 확인합니다.

- custom cereal reserved slot 3/4
- Event slot `@110/@111`
- `services.py`
- `CarrotPlanner`
- `LongitudinalPlanner`
- Carrot `plannerd.py`의 `main()` loop

`plannerd.py`의 관측 hook은 generic openpilot의 다른 구조를 가정하지 않고 실제 Carrot 소스의 `main()`을 기준으로 합니다. 이 형태는 historical live base `ce3d7630...`과 2026-09-09 확인한 upstream `dcce955c...`에서 모두 확인되었습니다.

판정:

```text
host surface compatible + overlay conflict 없음
  -> FAST_COMPATIBILITY_PATH

host surface drift 또는 overlay conflict
  -> REVALIDATION_REQUIRED
```

이 판정은 **관측 패치를 다시 검토해야 하는지**만 나타냅니다. 최신 Carrot 주행 기능의 안전성 승인 결과가 아닙니다.

업스트림에 eGPU 관련 파일이 존재하더라도 그것만으로 incompatibility로 판정하지 않습니다. 검사 범위는 오직 H1 overlay가 의존하는 host surface입니다.

## 9. 실차 적용 원칙

실제 comma에는 먼저 현재 `/data/openpilot` 상태를 read-only로 기록합니다.

- branch
- HEAD
- remotes
- `git status --short`
- local diff
- H1 관련 파일의 정확한 diff

그 뒤 기존 로컬 변경을 다음 네 범주로 분류합니다.

```text
OBSERVABILITY_REQUIRED
SIMULATOR_OFFLINE
UNRELATED
REMOVE
```

분류가 끝나기 전에는 기존 파일을 삭제하거나 `reset --hard`하지 않습니다. 또한 local diff의 recoverable copy가 확보되기 전에는 무조건적인 `git pull`도 하지 않습니다.

최종 overlay는 eGPU integration branch에서 코드를 빼내는 방식이 아니라 **그 시점의 최신 upstream `carrot-wip` 위에 필요한 H1 계측만 다시 적용하는 방식**을 사용합니다.

실차 검증 순서는 다음을 권장합니다.

```text
Gate A: live source inventory / backup
Gate B: 최소 observer extraction, eGPU dependency = 0
Gate C: observer OFF/ON 및 forced-failure control equivalence
Gate D: simulator H1 evidence ingestion
Gate E: comma offroad boot / service / logging 확인
```

Gate E 전에는 새 관측 패치를 정상 실주행 검증 완료로 취급하지 않습니다.

## 10. 현재 검증 경계

공개 저장소의 synthetic fixtures는 H1 evidence parser/validator의 계약을 검증하기 위한 것입니다. 실제 싼타페 route에 대한 H1 replay fidelity 검증은 실제 comma의 observability 상태를 확인하고 새 evidence를 확보한 뒤 진행합니다.

현재 공개 구현 완료 범위는 **evidence 구조/무결성 검증**까지입니다. 실제 controller bridge 실행, 실제 route에서의 output equality, 차량 Plant 식별/검증은 별도 단계로 남아 있습니다.
