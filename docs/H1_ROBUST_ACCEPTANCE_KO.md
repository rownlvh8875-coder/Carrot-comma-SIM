# H1 Robust Acceptance — 실주행 Controller Replay를 확정하는 방법

## 1. 목적

`H1_READY`는 evidence 구조가 replay 연구에 충분하다는 뜻이고, 하나의 실제 주행 구간에서 controller replay가 일치했다는 사실도 곧바로 **robust H1 acceptance**를 의미하지는 않습니다.

Robust H1은 특정 결과를 본 뒤 좋은 route만 고르는 것을 방지하기 위해 **검증 역할을 결과 확인 전에 고정**합니다.

## 2. 권장 prospective topology

```text
먼저 bounded moving replay로 도구/관측경로 검증
              ↓
acceptance contract 사전 고정
              ↓
첫 eligible distinct route   = development A
둘째 eligible distinct route = development B
셋째 eligible distinct route = sealed holdout
```

bounded seed route는 acceptance 역할이 사전 지정되지 않았다면 robust count에 소급 포함하지 않습니다.

## 3. Eligible route identity

같은 robust group의 route는 최소한 다음 항목이 동일해야 합니다.

- controller/source revision identity
- replay observability overlay identity
- vehicle/software reference identity
- controller-relevant applied configuration identity
- 사전 고정된 evidence window 규칙
- 실제 moving evidence 존재

이 중 하나가 달라지면 같은 acceptance group으로 임의 합치지 않습니다.

## 4. Development gate

Development A와 B는 같은 replay 계약을 사용합니다.

```text
recorded output count == replayed output count
native controller diff = 0 under the precommitted native tolerance
H1 trace semantic mismatch = 0
config snapshot semantics = exact
missing/invalid evidence = fail closed
```

두 development route가 모두 PASS해야 sealed holdout을 열 **자격**이 생깁니다. 자동으로 holdout을 열지는 않습니다.

## 5. Sealed holdout

세 번째 route는 결과를 미리 replay하지 않은 상태로 보존합니다.

```text
development A PASS
+ development B PASS
        ↓
별도 one-time holdout-open authorization
        ↓
동일한 unchanged gate로 holdout 1회 replay
```

holdout 결과가 실패하면 route 교체, tolerance 완화, ignore field 추가, 사후 metric 변경으로 PASS를 만들지 않습니다.

## 6. Robust H1 PASS의 권한

세 route가 계약대로 PASS하더라도 의미는 제한적입니다.

```text
controller replay fidelity robust PASS = 가능
H2 evidence-qualification review        = 시작 가능
H2 model fitting 자동 승인              = 아님
parameter tuning 자동 승인              = 아님
실차 Params/CAN write                    = 아님
실도로 안전성 인증                       = 아님
```

즉 H1은 **제어기 재현성이 충분히 검증됐다**는 단계이며, 이후 차량 반응 모델(H2)은 별도의 데이터·검증 계약을 거쳐야 합니다.

## 7. 공개/비공개 경계

공개 저장소에는 이 방법론과 일반화된 상태만 둡니다. 실제 route ID, raw-log hash, 장치 주소, 개인 설정값, 실제 차량 세부 provenance 및 개별 acceptance 결과는 private evidence layer에 둡니다.
