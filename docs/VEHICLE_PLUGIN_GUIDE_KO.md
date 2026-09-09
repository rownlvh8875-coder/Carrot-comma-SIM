# 새 차량 Plugin 추가 가이드

> 문서 역할과 최신 상태는 [`DOCUMENT_STATUS_KO.md`](DOCUMENT_STATUS_KO.md)를 참고합니다. 아래 `HYUNDAI_SANTA_FE_2022` 같은 값은 **software/controller identity 예시**이며 실제 차량의 등록연식·트림과 동일한 개념이 아닐 수 있습니다. 실제 vehicle identity는 H0에서 별도로 검증합니다.

## 목적

이 문서는 Carrot-comma-SIM에 새로운 차량을 추가할 때 따라야 할 기본 절차를 설명합니다.

핵심 원칙은 **"클래스를 만들었다 = 지원 차량"이 아니다**입니다.

차량별 Plant는 실제 또는 신뢰 가능한 차량별 증거와 검증 범위를 가져야 합니다.

---

## 1. 차량 ID 정의

차량을 식별할 수 있는 안정적인 **software/controller ID**를 정합니다.

예:

```text
HYUNDAI_SANTA_FE_2022
KIA_SORENTO_2023
HYUNDAI_IONIQ_5_2024
```

단순 마케팅 이름보다 실제 Controller/CarParams 쪽 식별자와 연결할 수 있는 이름이 좋습니다. 다만 software ID의 연식 문자열을 실제 등록연식으로 자동 해석하지 않습니다.

---

## 2. H0 — 데이터 identity/provenance 확인

먼저 새 차량 데이터가 정말 동일한 차량·동일한 소프트웨어 조건에서 나온 것인지 확인합니다.

확인 대상 예:

- 실제 차량 identity와 software fingerprint/CarParams의 대응
- Controller 계열과 commit
- 주요 설정값
- 로그 파일 무결성
- 동일하지 않은 설정/commit끼리 인과적으로 섞이지 않았는지

데이터 출처가 불명확하면 모델 fitting으로 넘어가지 않는 것이 원칙입니다.

---

## 3. Lateral 입력 경계 정의

조향 모델의 입력이 무엇인지 명확히 정의합니다.

예:

```text
Controller output
    ↓
steering command boundary
    ↓
EPS / vehicle response
    ↓
steering angle / yaw rate / lateral acceleration
```

어떤 신호가 최종 actuator 입력인지 검증 없이 추측하지 않습니다.

---

## 4. Longitudinal 입력 경계 정의

가속/감속도 같은 방식으로 실제 차량이 소비하는 명령 경계를 찾습니다.

후보 예:

- post-controller actuator request
- acceleration request
- braking request
- powertrain-specific output

앞차 상태나 Planner context를 Vehicle Plant 입력으로 잘못 흡수하면 Controller와 Plant의 역할이 섞이므로 주의합니다.

---

## 5. Axis model 구현

새 차량은 다음 인터페이스를 구현합니다.

```python
class MyVehicleLateral(LateralAxisPlant):
    ...

class MyVehicleLongitudinal(LongitudinalAxisPlant):
    ...
```

두 축을 공통 코어에 결합합니다.

```python
plant = CombinedVehiclePlant(
    metadata=metadata,
    lateral=MyVehicleLateral(),
    longitudinal=MyVehicleLongitudinal(),
)
```

차량 identity를 더 강하게 고정해야 한다면 싼타페처럼 strict wrapper를 추가할 수 있습니다.

---

## 6. `PlantMetadata` 작성

최소한 다음을 명확히 기록합니다.

```python
PlantMetadata(
    plant_id="...",
    vehicle="...",
    model_version="...",
    provenance="...",
    control_period_s=...,
    domain=PlantDomain(...),
)
```

`provenance`는 모델이 어떤 데이터/절차에서 나왔는지 설명하는 식별자입니다. 공개 저장소에서는 개인 route나 장치정보가 노출되지 않도록 익명화된 provenance를 사용해야 합니다.

---

## 7. Validated Domain 정의

모델이 실제 데이터로 확인된 범위를 기록합니다.

예:

- 최소/최대 속도
- 최대 조향 명령
- 최소/최대 종방향 가속 요청
- 횡가속 범위

검증하지 않은 범위까지 무조건 지원한다고 표시하지 않습니다.

---

## 8. 독립 검증 데이터 유지

모델을 만든 데이터와 모델을 평가하는 데이터를 분리하는 것을 권장합니다.

```text
Development data
      ↓
model identification

Independent validation data
      ↓
validation only
```

가능하다면 최종 holdout은 개발 중 반복 확인하지 않습니다.

---

## 9. 최소 공개 테스트

새 plugin은 최소한 다음 테스트를 가져야 합니다.

1. 올바른 vehicle metadata를 받는다.
2. 잘못된 vehicle identity를 strict wrapper가 거부한다.
3. control period mismatch를 거부한다.
4. validated domain 밖의 명령이 자동 통과하지 않는다.
5. NaN/Inf 입력을 거부한다.
6. `real_vehicle_write`가 false이다.
7. 같은 초기상태/입력에 대해 결정론적으로 동작한다.

---

## 10. 지원 상태 표기

차량 상태는 다음처럼 구분하는 것을 권장합니다.

```text
EXPERIMENTAL
  인터페이스/초기 모델만 존재

DEVELOPMENT_VALIDATED
  개발 데이터에서 기본 동작 확인

INDEPENDENTLY_VALIDATED
  독립 데이터에서 사전 정의한 검증 통과
```

공개 README에서는 이 구분을 명확하게 표시해 사용자가 "코드가 있다"와 "검증이 끝났다"를 혼동하지 않도록 합니다.

---

## 11. 절대 포함하지 않을 공개 자료

새 차량을 추가하더라도 public repo에는 다음을 커밋하지 않습니다.

- 원본 rlog/qlog
- 실제 route identifier
- 위치를 역추적할 수 있는 파일명/metadata
- comma IP/hostname/device ID
- SSH 정보
- 개인 PC 경로
- API key/token/password

필요한 경우 익명화된 통계 또는 synthetic sample을 별도로 만듭니다.

---

## 12. 최종 체크

새 차량을 "지원"으로 표시하기 전:

```text
[ ] software vehicle identity 고정
[ ] 실제 차량 identity와 software ID의 H0 대응 확인
[ ] H0 provenance 검토
[ ] lateral command boundary 확인
[ ] longitudinal command boundary 확인
[ ] PlantDomain 정의
[ ] unit tests 통과
[ ] independent validation 수행
[ ] real_vehicle_write = false
[ ] 공개 파일 privacy audit 통과
```

이 절차가 반복 가능해지면 첫 싼타페 모델에서 얻은 연구 방법을 다른 차량으로 확장할 수 있습니다.
