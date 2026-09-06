# 아키텍처 설명 — 범용 Carrot/openpilot 폐루프 시뮬레이터

## 1. 핵심 설계 원칙

이 프로젝트는 세 가지를 강하게 분리합니다.

```text
Controller  ≠  Vehicle Plant  ≠  World
```

- **Controller**는 어떻게 움직일지 결정합니다.
- **Vehicle Plant**는 그 명령을 받은 차량이 실제로 어떻게 반응할지 계산합니다.
- **WorldBackend**는 도로, 앞차, 주변 차량, 센서 조건을 제공합니다.

이 세 층을 섞지 않는 이유는 결과의 원인을 추적하기 위해서입니다.

예를 들어 앞차를 따라가지 못했을 때 원인이

- Controller의 판단인지,
- 차량 응답 모델의 지연인지,
- World의 앞차 궤적 설정인지

구분할 수 있어야 합니다.

---

## 2. 폐루프 구조

```text
┌───────────────────────────┐
│   Controller / Bridge     │
└─────────────┬─────────────┘
              │ PlantControl
              ▼
┌───────────────────────────┐
│   CombinedVehiclePlant    │
│ ┌─────────┐ ┌───────────┐ │
│ │ Lateral │ │Longitudinal│ │
│ └─────────┘ └───────────┘ │
└─────────────┬─────────────┘
              │ VehicleState
              ▼
┌───────────────────────────┐
│       WorldBackend        │
│ road / lead / traffic     │
└─────────────┬─────────────┘
              │ WorldObservation
              └──────────────→ 다음 Controller step
```

한 step이 끝날 때마다 새로운 `VehicleState`가 만들어지고, 그 상태가 다음 제어 판단에 다시 사용됩니다.

---

## 3. `PlantControl`

Controller가 Vehicle Plant에 넘기는 최소 명령입니다.

현재 공개 계약은 다음을 포함합니다.

- `dt_s`: 제어 주기
- `lateral_command`: 조향 관련 입력
- `longitudinal_accel_request_mps2`: 종방향 가속도 요청
- 입력의 출처를 기록하는 source 문자열

실제 Carrot/openpilot bridge를 붙일 때도 최종적으로 이 경계로 변환하는 방식이 목표입니다.

---

## 4. `VehicleState`

Vehicle Plant가 계산한 ego 차량 상태입니다.

현재 최소 상태는 다음과 같습니다.

- 시간
- 속도
- 종방향 가속도
- 횡가속도
- 조향각(선택)
- yaw rate(선택)
- x/y 위치

공개 초기 버전의 공통 Plant는 종방향 x 적분만 수행합니다. 정교한 lateral pose 적분은 별도 검증된 구성요소로 추가해야 합니다.

---

## 5. `WorldObservation`

WorldBackend가 Controller/Plant에 제공하는 외생(exogenous) 환경 정보입니다.

예:

- 도로 곡률
- 도로 roll
- 앞차 존재 여부
- 앞차 거리
- 상대속도
- 앞차 가속도
- 여러 주변 차량의 상대 상태

중요한 원칙은 **World가 ego 차량의 물리 반응을 소유하지 않는 것**입니다. World는 환경을 제공하고 Vehicle Plant가 ego 응답을 계산합니다.

---

## 6. `CombinedVehiclePlant`

차량별 Lateral / Longitudinal 모델을 조립하는 공통 코어입니다.

```text
CombinedVehiclePlant
   ├─ LateralAxisPlant
   └─ LongitudinalAxisPlant
```

제조사나 차종 상수는 공통 클래스 안에 넣지 않습니다. 차량 ID와 검증정보는 `PlantMetadata`를 통해 전달합니다.

---

## 7. 왜 `CombinedSantaFePlant`를 따로 유지하는가?

싼타페는 이 프로젝트의 첫 reference vehicle입니다.

그래서 `CombinedSantaFePlant`는 다음을 보장합니다.

```text
metadata.vehicle == HYUNDAI_SANTA_FE_2022
```

다른 차량 metadata를 실수로 넣으면 즉시 실패합니다.

공통 코어를 범용화하면서도 기존 싼타페 evidence identity를 흐리지 않기 위한 장치입니다.

---

## 8. Validated Domain

Vehicle Plant는 아무 속도/명령에서나 정확하다고 가정하지 않습니다.

각 Plant는 `PlantDomain`을 통해 검증된 범위를 선언할 수 있습니다.

예:

```text
0 ≤ speed ≤ 35 m/s
-3 ≤ requested accel ≤ 2 m/s²
|lateral command| ≤ validated limit
```

범위를 벗어나면 기본 동작은 **fail-closed**입니다.

즉, 그럴듯하게 외삽(extrapolation)해서 결과를 계속 내지 않고 명시적으로 차단합니다.

---

## 9. Teacher Force

특정 연구에서는 검증 범위를 벗어난 구간을 실제 기록 상태로 강제 연결하는 diagnostic이 필요할 수 있습니다.

이때만 명시적인 `teacher_force` callback을 사용할 수 있습니다.

그 step은 trace에 `teacher_forced=True`로 남으며 정상 Plant 검증 증거와 섞이면 안 됩니다.

---

## 10. Synthetic scenario의 역할

Synthetic world는 다음에 유용합니다.

- cut-in / cut-out
- 급감속 lead
- stop-and-go
- 센서 지연
- 메시지 누락
- extreme parameter sweep
- regression test

하지만 synthetic 결과만으로 실제 도로 안전성을 주장하지 않습니다.

```text
Synthetic stress result
       ≠
Real-road acceptance evidence
```

---

## 11. 장기 구조

```text
Controller Adapters
   ├─ Carrot
   ├─ openpilot
   └─ test controller
          │
          ▼
  Common Controller API
          │
          ▼
  CombinedVehiclePlant
   ├─ SantaFe plugin
   ├─ Vehicle B plugin
   └─ Vehicle C plugin
          │
          ▼
      WorldBackend
   ├─ Parametric world
   ├─ MetaDrive adapter
   ├─ SUMO adapter
   └─ CommonRoad adapter
          │
          ▼
 Scenario / Regression Engine
```

목표는 특정 차량에 종속된 하나의 시뮬레이터가 아니라 **차량 Plant를 교체할 수 있는 공통 검증 플랫폼**입니다.
