# 시뮬레이터에 차량 세팅을 넣으면 무엇이 나오는가?

기준일: 2026-09-09

이 문서는 Carrot-comma-SIM을 처음 보는 사람이 **무엇을 입력하고, 내부에서 어떤 계산을 하며, 최종적으로 어떤 결과를 받는지** 이해하기 쉽게 설명합니다.

> 아래 숫자는 구조를 설명하기 위한 **예시 값**입니다. 아직 실제 싼타페 H1/H2 검증으로 확정된 측정값이나 추천값이 아닙니다.

## 1. 한 문장으로 설명

Carrot-comma-SIM의 목표는 다음 질문에 답하는 것입니다.

> **“이 Carrot 설정으로 이런 도로 상황을 만났을 때, 제어기는 어떤 명령을 만들고 내 차량은 그 명령에 어떻게 반응하며, 그 결과가 현재 설정보다 더 안정적이고 편안한가?”**

즉 입력은 단순한 파라미터 목록이 아니고, 출력도 점수 하나가 아닙니다.

```text
차량 + Carrot 설정 + 주행 시나리오
              ↓
      Controller 계산
              ↓
     Vehicle Plant 반응
              ↓
       시간축 차량상태
              ↓
 Safety / Comfort / Tracking
              ↓
   현재 세팅과 후보 세팅 비교
```

## 2. 무엇을 입력하는가?

### A. Carrot 설정

실제 제어에 영향을 주는 파라미터를 읽습니다.

예:

- 차간거리 / follow 계열
- 가속 반응 계열
- 감속 반응 계열
- 정지거리 / 정차 접근 계열
- 출발 반응
- lead 추종 관련 설정
- curve 감속 관련 설정
- 조향 gain / smoothness 관련 설정

UI 색상처럼 주행동작과 관계없는 값은 튜닝 후보에서 제외합니다.

### B. 차량 모델

같은 제어명령이라도 차량마다 반응이 다릅니다.

Vehicle Plant는 다음과 같은 실제 차량 특성을 표현합니다.

- 가속/감속 응답
- 브레이크 및 구동계 지연
- 조향 응답
- 차량 질량, 휠베이스 등 물리 특성
- 속도별 응답 차이
- 검증된 동작범위(Validated Domain)

### C. 시험할 주행상황

예를 들어 다음을 설정할 수 있습니다.

```text
내 차 속도      = 80 km/h
앞차 속도       = 70 km/h
초기 차간거리   = 45 m
3초 뒤 앞차     = 70 → 40 km/h 급감속
도로            = 직선
```

또는 cut-in, cut-out, stop-and-go, 정차 후 출발, 고속 커브 같은 시나리오를 반복할 수 있습니다.

## 3. 내부에서는 어떤 순서로 계산하는가?

### Step 1 — Controller가 판단

예를 들어 현재 상황에서 Carrot이 다음과 같이 판단했다고 가정합니다.

```text
현재 속도       = 80 km/h
앞차 속도       = 70 km/h
거리            = 45 m
Carrot 가속도 요청 = -0.25 m/s²
```

이 값은 **제어기가 원하는 명령**입니다.

### Step 2 — Vehicle Plant가 실제 차량 반응을 계산

차량은 명령값대로 즉시 움직이지 않습니다.

예를 들어 싼타페 Plant가 다음처럼 계산할 수 있습니다.

```text
Controller 요청       = -0.25 m/s²
차량 예상 실제응답     = -0.18 m/s²
```

엔진/변속기/브레이크/차량질량/응답지연 때문에 명령과 실제 반응 사이에 차이가 생깁니다.

### Step 3 — 새로운 차량상태를 계산

그 결과 새로운 속도와 위치가 만들어집니다.

```text
시간 0.0 s   속도 80.0 km/h   거리 45.0 m
시간 1.0 s   속도 79.5 km/h   거리 42.3 m
시간 2.0 s   속도 78.8 km/h   거리 39.8 m
```

### Step 4 — 새 상태를 다시 Controller에 입력

이 새로운 상태가 다시 Carrot의 다음 판단 입력이 됩니다.

이 과정을 수십~수천 step 반복합니다.

```text
Controller → Vehicle Plant → VehicleState → World → Controller → ...
```

이것이 이 프로젝트에서 말하는 **Closed-loop simulation**입니다.

## 4. 앞차가 급제동하면 어떻게 보이는가?

설명용 예시입니다.

3초 시점에 앞차가 70 km/h에서 40 km/h로 급감속한다고 가정합니다.

Carrot의 명령은 다음처럼 강해질 수 있습니다.

```text
3.00 s   Carrot 요청       -1.80 m/s²
```

하지만 Vehicle Plant는 차량의 실제 지연을 반영합니다.

```text
3.00 s   실제 차량반응     -0.30 m/s²
3.10 s   실제 차량반응     -0.70 m/s²
3.20 s   실제 차량반응     -1.35 m/s²
3.30 s   실제 차량반응     -1.70 m/s²
```

따라서 시뮬레이터는 **“Carrot이 무엇을 명령했는가”와 “차가 실제로 어떻게 움직였는가”를 분리해서 보여주는 것**이 핵심입니다.

## 5. 최종 출력은 무엇인가?

### A. 시간축 데이터

예:

- ego speed
- lead speed
- gap distance
- relative speed
- requested acceleration
- actual simulated acceleration
- steering command / steering response
- lateral position error
- TTC / THW

즉 매 step의 상태를 기록합니다.

### B. 요약 결과

한 시나리오가 끝나면 다음처럼 요약할 수 있습니다.

| 항목 | 설명용 결과 |
|---|---:|
| 최초 속도 | 80 km/h |
| 최소 앞차 거리 | 22.4 m |
| 최소 TTC | 2.6 s |
| 최대 제어 감속 요청 | -1.80 m/s² |
| 실제 최대 감속 | -1.72 m/s² |
| 제어→차량 반응 지연 | 0.18 s |
| peak jerk | 1.3 m/s³ |
| 앞차 재추종 | 성공 |
| 충돌 | 없음 |

### C. 그래프

최종 도구에서는 다음 그래프를 함께 보는 것이 목표입니다.

```text
속도 vs 시간
차간거리 vs 시간
가속도 vs 시간
jerk vs 시간
TTC/THW vs 시간
조향명령 vs 차량응답
차선 중심 오차 vs 시간
```

단일 점수만 보여주지 않고 **왜 그 점수가 나왔는지 원래 물리량을 같이 보여주는 것**이 원칙입니다.

## 6. 현재 세팅과 후보 세팅은 어떻게 비교하는가?

현재 세팅을 Baseline으로 고정합니다.

예를 들어 설명용으로:

```text
현재 세팅 A
Follow 계열      = 1.10
Accel 계열       = 1.00
Decel 계열       = 1.00
StopDistance     = 4.0
```

후보 B를 만들었다고 가정합니다.

```text
후보 B
Follow 계열      = 1.22
Accel 계열       = 0.94
Decel 계열       = 0.97
StopDistance     = 4.4
```

둘을 **완전히 동일한 시나리오들**에서 반복합니다.

예시 결과:

| 지표 | 현재 A | 후보 B |
|---|---:|---:|
| 최소 TTC | 2.2 s | 2.9 s |
| 최소 거리 | 18 m | 24 m |
| peak jerk | 2.1 | 1.2 |
| gap RMS error | 5.1 m | 3.4 m |
| 추종 응답시간 | 1.1 s | 0.9 s |

이 경우 후보 B는 예시상:

- 차간 여유 증가
- 급감속 위험 여유 개선
- jerk 감소
- 목표 차간거리 오차 감소
- 추종 응답 개선

이라는 식으로 해석할 수 있습니다.

## 7. Safety / Comfort / Tracking은 어디서 나오는가?

### Safety-related performance

예:

- TTC / THW
- 최소 차간거리
- 제동여유
- cut-in 회복
- 차선 오차
- 조향 포화
- 검증된 차량동역학 범위 초과 여부

충돌, 검증범위 초과 등 **Hard Gate를 위반하면 다른 점수가 좋아도 후보에서 탈락**합니다.

### Comfort

예:

- longitudinal jerk
- lateral jerk
- 불필요한 가감속 반복
- 정차 직전 울컥임
- 출발 순간 튐
- 조향 oscillation

### Tracking

예:

- 목표거리와 실제거리 오차
- 상대속도 오차
- 앞차 변화에 대한 응답시간
- overshoot
- settling time
- hunting 횟수

세부 계약은 [`SCORING_AND_TUNING_KO.md`](SCORING_AND_TUNING_KO.md)를 따릅니다.

## 8. “안전성과 승차감 위주로 추천해줘”는 어떻게 처리하는가?

먼저 Hard Gate를 통과한 후보만 남깁니다.

그 다음 사용자 선호를 순위에 반영할 수 있습니다.

예:

```text
Safety-related performance = 60%
Comfort                    = 30%
Tracking                   = 10%
```

단, 이 비율은 **위험한 세팅을 안전한 세팅으로 만들어주는 가중치가 아닙니다.**

Hard Gate 실패 후보는 100점짜리 Comfort라도 탈락합니다.

최종적으로는 다음처럼 보여주는 것이 목표입니다.

```text
추천 후보 B

Safety-related performance : 개선
Comfort                    : 개선
Tracking                   : 개선

예상 Trade-off
- 차간거리는 더 여유로움
- 급감속시 필요한 최대 감속 감소
- 정차/저속 jerk 감소
- 출발 반응은 약간 느려질 수 있음
```

## 9. 파라미터가 많으면 어떻게 하는가?

Carrot에는 많은 파라미터가 있으므로 모든 조합을 무식하게 전수조사하지 않습니다.

목표 구조는:

```text
주행에 영향을 주는 파라미터 선별
        ↓
안전한 탐색범위 정의
        ↓
현재값 주변 후보 생성
        ↓
시나리오 batch 실행
        ↓
Hard Gate 탈락 제거
        ↓
Pareto / worst-case / 사용자 선호 비교
        ↓
상위 후보 제시
```

예를 들어 수백~수천 후보를 시뮬레이션해도 최종적으로는 **현재값보다 무엇이 얼마나 좋아지고 무엇이 나빠지는지** 설명할 수 있어야 합니다.

## 10. 추천 결과가 자동으로 실차에 적용되는가?

아닙니다.

```text
시뮬레이터 후보 생성
  ↓
Hard Gate
  ↓
반복 시나리오 평가
  ↓
추천 후보
  ↓
사람의 검토
  ↓
별도 실차 검증
  ↓
채택 여부 결정
```

시뮬레이터 점수가 실제 차량 Params write 권한을 만들지 않습니다.

## 11. 현재 구현 상태와 최종 목표를 구분

현재 공개 코어에는 이미:

- World / Vehicle Plant / Controller 경계
- closed-loop 공통 계약
- scenario catalog
- H1 schema-v6 evidence 구조검증
- synthetic example / CI

이 구현되어 있습니다.

반면 다음은 실제 comma evidence와 추가 구현/검증이 필요한 단계입니다.

- 실제 Carrot controller replay fidelity 완성
- 실제 싼타페 longitudinal Plant 최종 검증
- 실차 기반 Safety/Comfort/Tracking calibration
- 대규모 parameter sweep / ranking 자동화
- 최종 사용자용 dashboard/그래프 UI

따라서 이 문서의 상세 결과표는 **완성형 시스템이 어떤 결과물을 제공하는지 설명하는 목표 인터페이스 예시**이며, 검증되지 않은 실제 성능 수치로 읽으면 안 됩니다.

## 12. 결국 이 프로젝트의 결과물은 무엇인가?

최종적으로 사용자가 보고 싶은 것은 단순한 “추천값 4개”가 아닙니다.

```text
현재 내 설정
   ↓
동일한 가상 주행상황 수백~수천 회
   ↓
Carrot 판단 + 내 차량 예상 반응
   ↓
Safety / Comfort / Tracking 원시지표
   ↓
현재 설정 vs 후보 설정 비교
   ↓
왜 이 후보가 더 좋은지 설명
```

즉 **“내 Carrot 설정을 실제 도로에서 무작정 바꿔보기 전에, 내 차량 모델을 이용해 반복 검증하고 trade-off를 숫자와 그래프로 확인하는 도구”**가 Carrot-comma-SIM의 최종 목표입니다.
