# 시뮬레이터 평가·파라미터 추천 기준

기준일: 2026-09-09

## 1. 목적

Carrot-comma-SIM은 파라미터 조합을 단순히 "좋다/나쁘다"로 판단하지 않습니다. 시뮬레이션 결과를 **안전 관련 성능(Safety-related performance)**, **승차감(Comfort)**, **추종성(Tracking)**으로 나누어 측정하고, 하드 제한을 통과한 후보만 사용자 선호에 따라 순위를 매기는 것을 목표로 합니다.

여기서 `Safety`는 실제 도로 안전 인증이나 안전보증을 뜻하지 않습니다. 시뮬레이터가 측정 가능한 충돌위험, 제동여유, 차간거리, 차선유지 등의 **안전 관련 성능 지표**를 뜻합니다.

## 2. 평가 순서

```text
현재 차량/Carrot 설정 = Baseline
        ↓
동일 시나리오에서 후보 파라미터 조합 실행
        ↓
모델/증거/Validated Domain 확인
        ↓
Hard Gate 적용
        ↓
통과 후보의 Safety / Comfort / Tracking 계산
        ↓
Baseline 대비 개선/악화량 계산
        ↓
사용자 선호 가중치 + Pareto 비교
        ↓
추천 후보와 Trade-off 설명
```

승차감 점수가 높아도 Hard Gate를 위반한 후보는 추천하지 않습니다.

## 3. Hard Gate — 점수보다 우선하는 탈락조건

정확한 수치 임계값은 차량 모델과 시나리오의 검증범위에서 정합니다. 모든 차량에 하나의 TTC/감속 임계값을 임의로 고정하지 않습니다.

대표적인 탈락조건은 다음과 같습니다.

- 충돌 발생
- 시나리오가 요구하는 최소 TTC/THW 기준 위반
- 차량 Plant의 검증된 가속·감속·조향 범위 초과
- 필요한 제동량이 검증된 차량 응답범위를 초과
- 차선유지 시나리오에서 허용 경계 이탈
- 제어 출력 포화 또는 비정상 진동
- H0/H1 evidence가 부족하여 결과 신뢰성을 보장할 수 없음
- Vehicle Plant가 Validated Domain 밖에서 외삽되어야 하는 경우
- controller/replay 오류 또는 메시지 무결성 실패

Hard Gate 임계값은 버전과 근거를 함께 기록하며, 후보를 유리하게 만들기 위해 사후에 낮추지 않습니다.

## 4. Safety-related performance

### 종방향

- TTC(Time To Collision) 최소값 및 위험구간 체류시간
- THW(Time Headway) 최소값과 목표 대비 여유
- 최소 실제 차간거리
- 급감속 lead/cut-in 이후 제동여유
- 요구 감속도와 차량의 검증된 감속능력 간 margin
- 위험상태에서 정상 차간거리로 회복하는 시간
- 충돌/near-collision event 수

### 횡방향

- 차선 중심 오차 및 최대 횡오차
- 횡가속도와 lateral jerk
- steering saturation/overshoot
- yaw-rate 및 조향 응답의 안정성
- 차선 경계 침범 여부

Safety 점수는 Hard Gate를 통과한 후보끼리 비교하기 위한 값입니다. 위험한 후보를 높은 다른 점수로 상쇄하지 않습니다.

## 5. Comfort

승차감은 "부드럽게 느껴진다"를 가능한 한 물리량으로 환산합니다.

### 종방향 Comfort

- RMS acceleration
- peak acceleration/deceleration
- RMS jerk
- peak jerk
- 가속↔감속 방향전환 빈도
- stop 직전 jerk와 overshoot
- start 시 초기 jerk와 튀어나감 정도
- 앞차 추종 중 throttle/brake hunting 빈도

### 횡방향 Comfort

- lateral acceleration
- lateral jerk
- steering rate / steering acceleration
- 좌우 조향 반전 빈도
- steering oscillation amplitude/frequency
- 차선 중심 주변의 불필요한 흔들림

Comfort는 단순히 반응을 느리게 만드는 것을 목표로 하지 않습니다. 반응이 지나치게 둔해 Tracking 또는 Safety-related performance가 악화되면 높은 추천순위를 받을 수 없습니다.

## 6. Tracking

추종성은 "앞차에 가까이 붙는 정도"가 아니라 **목표 차간거리/속도 관계를 안정적으로 따라가는 정도**입니다.

대표 지표:

- target gap 대비 actual gap RMSE
- 상대속도(relative speed) RMSE
- lead 속도변화에 대한 응답 지연
- overshoot / undershoot
- settling time
- steady-state gap error
- cut-in/cut-out 후 목표상태 회복시간
- 가속·감속 hunting 횟수
- stop-and-go에서 출발/정지 추종 오차

평균값이 좋아도 큰 진동을 반복하면 좋은 Tracking으로 평가하지 않습니다.

## 7. 점수 정규화

각 raw metric은 그대로 더하지 않습니다. 단위가 서로 다르기 때문입니다.

권장 방식:

1. Hard Gate와 Validated Domain을 먼저 적용합니다.
2. 각 metric을 차량/시나리오별 기준범위 또는 baseline 대비 변화량으로 정규화합니다.
3. `0~100` 같은 표시용 점수로 변환할 때 원래 raw metric을 함께 보존합니다.
4. aggregate score와 함께 TTC, THW, jerk, gap error 등 원자료를 항상 표시합니다.

즉 `Safety 92`만 보여주지 않고 **왜 92인지 설명 가능한 raw metric**을 같이 보여주는 것이 원칙입니다.

## 8. 사용자 선호 가중치

Hard Gate를 통과한 후보에 한해 사용자 선호를 적용합니다.

예시 프로필:

```text
Balanced comfort/safety
Safety-related performance 60%
Comfort                    30%
Tracking                   10%
```

이 값은 프로젝트의 영구 표준이 아니라 사용자 선택 프로필의 예입니다.

향후 예:

- `Safe`: 안전 관련 성능 우선
- `Comfort`: 승차감 우선, 단 Hard Gate는 동일
- `Balanced`: 안전/승차감 균형
- `Highway`: 고속 추종·차간 안정성 강조
- `City`: stop-and-go·cut-in·정차 승차감 강조

## 9. Baseline 대비 추천

파라미터 추천의 기본 기준은 **현재 사용 중인 세팅을 baseline으로 삼는 것**입니다.

추천 결과는 최소한 다음을 보여줍니다.

- 변경된 파라미터와 변경량
- Safety/Comfort/Tracking 점수 변화
- TTC/THW/min gap/jerk/gap RMSE 같은 raw metric 변화
- 좋아진 시나리오와 악화된 시나리오
- 가장 취약한 worst-case scenario
- Validated Domain 밖 결과가 있었는지
- 실제 차량 검증이 추가로 필요한 이유

현재 설정보다 어떤 측면도 명확히 좋아지지 않는 후보는 "추천"으로 포장하지 않습니다.

## 10. 파라미터 탐색 원칙

Carrot 파라미터가 많더라도 모든 값을 무작정 전수조합하지 않습니다.

1. UI/표시 등 주행과 무관한 파라미터 제외
2. 제어 영향 파라미터를 기능군으로 분류
3. 민감도 분석으로 영향이 거의 없는 축 제거
4. 안전한 범위 안에서 coarse sweep
5. 상위 후보 주변을 finer sweep
6. 여러 시나리오와 perturbation에서 robustness 확인
7. holdout 시나리오에서 재검증

후보는 단일 평균점수보다 **Pareto frontier와 worst-case 성능**을 함께 봅니다.

## 11. 자동 적용 금지

시뮬레이터가 높은 점수를 낸 파라미터를 실제 comma에 자동으로 쓰지 않습니다.

```text
Simulation recommendation
        ↓
사람의 검토
        ↓
보수적 실차 검증 계획
        ↓
실차 관측
        ↓
채택/보류/폐기
```

실차 Params 변경은 별도 명시적 승인과 검증 절차를 거쳐야 합니다.

## 12. 공개/비공개 데이터 경계

이 문서의 평가공식·metric 정의·synthetic 예시는 공개할 수 있습니다. 반면 다음은 비공개 연구자료로 유지합니다.

- 실제 차량의 개인 현재 세팅값
- 원본 rlog/qlog와 route 식별정보
- 실제 주행 기반 parameter candidate 결과
- 개인 차량별 calibration/validated-domain evidence
- 실주행 기반 추천 세팅 및 결과 이력

세부 규칙은 `docs/PUBLIC_PRIVATE_REPO_POLICY_KO.md`를 따릅니다.
