# Carrot-comma-SIM

> **Carrot/openpilot 계열 제어기를 실제 차량 없이 반복 시험하기 위한 범용 폐루프(Closed-loop) 차량 시뮬레이터 연구 프로젝트**  
> 첫 번째 Reference Vehicle은 `HYUNDAI_SANTA_FE_2022`입니다.

[한국어](README.md) · [English](README_EN.md) · [현재 프로젝트 상태](docs/PROJECT_STATUS_KO.md) · [평가·튜닝 기준](docs/SCORING_AND_TUNING_KO.md) · [공개/비공개 정책](docs/PUBLIC_PRIVATE_REPO_POLICY_KO.md) · [시뮬레이션 결과는 어떻게 나오는가?](docs/HOW_SIMULATION_OUTPUT_WORKS_KO.md)

---

## 1. 이 프로젝트는 무엇인가?

Carrot/openpilot의 주행 제어 로직을 개선할 때마다 실제 차를 타고 같은 상황을 다시 만드는 것은 어렵고 위험하며 시간이 많이 듭니다.

이 프로젝트의 목표는 **실제 제어기와 차량의 반응 모델을 분리**하여 컴퓨터 안에서 다음 고리를 반복 실행하는 것입니다.

```text
Carrot / openpilot Controller
            ↓
       PlantControl
            ↓
   CombinedVehiclePlant
      ├─ Lateral Plant      (조향 반응)
      └─ Longitudinal Plant (가속/감속 반응)
            ↓
        VehicleState
            ↓
        WorldBackend
   도로 / 앞차 / 교통 / 센서
            ↓
   다시 Controller로 입력
```

이를 **폐루프(Closed-loop)**라고 합니다. 제어기의 출력이 차량 상태를 바꾸고, 바뀐 차량 상태가 다시 제어기의 다음 입력이 되는 구조입니다.

### 실제로 어떤 결과가 나오는가?

```text
현재 차량/Carrot 세팅 + 주행 시나리오
             ↓
      Carrot Controller 판단
             ↓
   가속/감속/조향 제어명령
             ↓
       Vehicle Plant 반응
             ↓
 속도·차간거리·가속도·조향 등 시간축 결과
             ↓
 Safety-related performance / Comfort / Tracking
             ↓
      현재 세팅 vs 후보 세팅 비교
```

예를 들어 80 km/h에서 앞차가 급감속하면, **Carrot이 언제 얼마만큼 감속을 요청했는지**, **차량 모델이 실제로 얼마의 지연과 감속으로 반응했는지**, 그 결과 **최소 차간거리·TTC·jerk·추종오차가 어떻게 변했는지**를 비교합니다. 최종 결과는 추천값 하나가 아니라 원시 지표, 그래프, worst-case와 trade-off까지 보여주는 것이 목표입니다.

자세한 설명과 결과표 예시는 [`docs/HOW_SIMULATION_OUTPUT_WORKS_KO.md`](docs/HOW_SIMULATION_OUTPUT_WORKS_KO.md)를 참고합니다. 문서의 숫자는 구조 설명용 예시이며 실제 차량 검증값이 아닙니다.

---

## 2. 왜 싼타페 전용이 아니라 범용 구조인가?

현재 실제 데이터와 검증의 기준 차량은 **2022 Hyundai Santa Fe**이지만, 시뮬레이터의 공통 코어는 차량에 종속되지 않도록 설계합니다.

```text
CombinedVehiclePlant          ← 공통 코어
        │
        ├─ CombinedSantaFePlant   ← 첫 Reference Vehicle
        ├─ FutureSorentoPlant
        ├─ FutureIoniq5Plant
        └─ FutureOtherVehiclePlant
```

차량이 바뀌면 주로 다음 부분만 새 데이터로 식별·검증합니다.

- 조향(EPS) 응답
- 가속/감속 응답
- 브레이크 및 구동계 지연
- 차량 질량·휠베이스·관성 등 물리 특성
- CarController 출력과 실제 차량 반응의 관계
- 차량별 유효 동작 범위(Validated Domain)

도로, 앞차, 컷인/컷아웃, 시나리오 우선순위, 반복 실행, 결과 기록 같은 프레임워크는 재사용하는 것이 목표입니다.

---

## 3. 현재 연구 상태

| 영역 | 상태 | 의미 |
|---|---|---|
| 범용 World / Plant 분리 | ✅ 구현 | 가상 도로가 실제 차량 Plant를 몰래 대체하지 않도록 분리 |
| 범용 `CombinedVehiclePlant` | ✅ 구현 | 다른 차량 플러그인을 추가할 수 있는 공통 코어 |
| Santa Fe reference wrapper | ✅ 구현 | `HYUNDAI_SANTA_FE_2022` 차량 ID를 엄격하게 고정 |
| 조향(Lateral) 모델 | ✅ 기준 모델 동결 | 추가 데이터에 맞춰 임의로 계속 재학습하지 않는 기준 모델 보유 |
| 종방향(Longitudinal) 모델 | 🚧 연구 중 | 실주행 관측 데이터와 정확한 제어 입력 경계 검증 진행 중 |
| 시나리오 카탈로그 | ✅ 구현 | 노출도·중요도·복잡도·커버리지 기준의 결정론적 우선순위 |
| H1 evidence 구조 검증 | ✅ 구현 | schema-v6 전체 trace, config SHA, snapshot identity, trigger/radar 의미 일관성을 fail-closed 검증 |
| 실제 H1 replay fidelity | 🚧 실차 evidence 대기 | 실제 comma에서 새 관측 로그를 확보한 뒤 controller output 재현성을 검증 |
| 파라미터 후보 평가/추천 | 📐 기준 문서화 | Safety-related performance / Comfort / Tracking + Hard Gate 기반. 실제 comma 자동 적용은 금지 |
| 실제 차량 쓰기 | ⛔ 없음 | 이 공개 시뮬레이터 코어는 실차 설정/제어값을 쓰지 않음 |

`H1_READY`는 evidence 구조가 deterministic replay 연구를 시작할 만큼 충분하다는 뜻일 뿐, 실제 controller replay 일치나 실도로 안전성을 뜻하지 않습니다. 자세한 계약은 [`docs/H1_OBSERVABILITY_KO.md`](docs/H1_OBSERVABILITY_KO.md)를 참고합니다.

### 지금 바로 다음 단계

현재 저장소 쪽 H1 구조 검증은 구현돼 있습니다. 다음 실증 단계는 **실제 comma의 `/data/openpilot` 상태를 먼저 read-only로 확인하는 것**입니다.

```text
branch / HEAD / remotes
        ↓
git status --short / local diff
        ↓
기존 H1 observability 변경 분류
        ↓
백업 후 최신 carrot-wip 동기화 검토
        ↓
최소 observability overlay 유지
        ↓
새 실제 H1 evidence 확보 및 replay fidelity 검증
```

초기 inventory가 끝나기 전에는 `reset --hard`, 무조건적인 `git pull`, 기존 H1 파일 삭제를 하지 않습니다. 세부 현황은 [`docs/PROJECT_STATUS_KO.md`](docs/PROJECT_STATUS_KO.md)에 정리합니다.

이 저장소는 **연구용 공개판**입니다. 비공개 연구 저장소의 실제 주행 원본 로그, 장치 식별정보, 네트워크 정보, 개인 경로 및 민감한 provenance 자료는 포함하지 않습니다.

---

## 4. H0 / H1 / H2를 쉽게 설명하면

이 프로젝트에서는 모델을 바로 튜닝하지 않고 증거 수준을 단계적으로 나눕니다.

### H0 — 데이터 신원 확인

> "이 로그가 정말 어떤 차량, 어떤 코드, 어떤 조건에서 만들어졌는가?"

차량 종류, 소프트웨어 버전, 설정, 데이터 출처가 섞이면 모델이 잘못된 원인을 학습할 수 있으므로 먼저 데이터의 정체성을 확인합니다.

### H1 — 제어기 재현성 확인

> "같은 입력을 주면 당시 제어기가 만들었던 출력을 다시 재현할 수 있는가?"

이를 **Replay Fidelity(재생 충실도)**라고 합니다. H1이 충분하지 않으면 차이가 제어기 때문인지 차량 때문인지 분리하기 어렵습니다.

현재 공개 코어에는 schema-v6 H1 evidence의 구조적 충분성을 검사하는 계층이 구현되어 있습니다. 실제 재현 충실도 판정은 실제 comma evidence로 별도 수행합니다.

파라미터 후보 평가는 [`docs/SCORING_AND_TUNING_KO.md`](docs/SCORING_AND_TUNING_KO.md)의 계약을 따릅니다. Safety-related performance는 TTC/THW/제동여유/차선오차 등, Comfort는 jerk/가감속·조향 진동 등, Tracking은 gap error/상대속도 오차/응답시간·settling 등을 사용합니다. Hard Gate를 위반한 후보는 다른 점수가 좋아도 추천하지 않으며, 추천 결과가 실제 차량 Params를 자동 변경하지 않습니다.

### H2 — 차량 반응 모델 확인

> "제어기가 명령했을 때 실제 차량이 어떻게 움직였는가?"

여기서 조향·가속·감속·지연 등을 Vehicle Plant로 모델링합니다.

```text
H0  데이터 신뢰
 ↓
H1  Controller replay 신뢰
 ↓
H2  Vehicle Plant 신뢰
 ↓
Closed-loop simulation
 ↓
Synthetic stress / scenario testing
```

---

## 5. 중요한 용어

- **Vehicle Plant**: 제어 명령을 받았을 때 차량이 어떻게 반응하는지를 계산하는 차량 동역학/응답 모델
- **WorldBackend**: 도로, 앞차, 주변 차량, 센서 조건을 제공하는 가상 환경
- **Reference Vehicle**: 모델링과 검증 절차를 처음 완성하는 기준 차량
- **Replay**: 과거 입력을 다시 넣어 과거 제어 출력을 재현하는 과정
- **Fidelity**: 재현 결과가 실제 기록과 얼마나 일치하는지 나타내는 충실도
- **Provenance**: 데이터가 언제·어디서·어떤 코드/설정으로 만들어졌는지에 대한 출처 정보
- **Observability**: 제어기가 실제로 사용한 입력·설정·내부 상태를 관측할 수 있는 정도
- **Holdout**: 모델 개발에 사용하지 않고 마지막 검증용으로 남겨두는 독립 데이터
- **Fail-closed**: 조건이 불확실하면 편의상 통과시키지 않고 실행을 차단하는 원칙
- **Validated Domain**: 해당 차량 모델이 데이터로 검증된 속도·명령 범위
- **Cut-in / Cut-out**: 다른 차량이 내 차 앞으로 들어오거나 앞차가 차선을 빠져나가는 상황

---

## 6. 안전 및 연구 원칙

이 공개판은 다음 원칙을 코드 계약으로 유지합니다.

1. 외부 World simulator가 검증된 차량 Plant를 자동으로 대체하지 않습니다.
2. 검증 범위를 벗어난 입력은 기본적으로 차단합니다.
3. Synthetic scenario 결과를 실제 도로 안전성 증거로 자동 승격하지 않습니다.
4. 단일 step fitting 결과를 closed-loop 검증 결과라고 부르지 않습니다.
5. 시나리오 점수나 behavior metric이 자동으로 튜닝 권한을 만들지 않습니다.
6. 공개 시뮬레이터 코어는 실제 차량에 값을 쓰지 않습니다.
7. H1 evidence가 누락·변조·불일치하면 추측해서 복구하지 않고 `H1_HOLD` 또는 `H1_ERROR`로 처리합니다.

> **이 프로젝트는 운전자 보조 시스템의 연구/시뮬레이션 도구이며, 실제 도로 안전을 보증하거나 운전자의 주의 의무를 대체하지 않습니다.**

---

## 7. 빠른 실행

Python 3.11 이상을 권장합니다.

```bash
git clone https://github.com/rownlvh8875-coder/Carrot-comma-SIM.git
cd Carrot-comma-SIM
python -m unittest discover -s tests -p 'test_*.py' -v
python examples/basic_closed_loop.py
```

H1 synthetic evidence 계약 확인:

```bash
python scripts/inspect_h1_evidence.py examples/h1_evidence_ready.jsonl
python scripts/inspect_h1_evidence.py examples/h1_evidence_missing_config.jsonl
```

openpilot checkout의 H1 overlay host surface를 **읽기 전용**으로 확인:

```bash
python scripts/check_openpilot_overlay.py /path/to/openpilot
```

현재 공개 코어는 외부 Python 패키지 없이 동작하도록 구성했습니다.

---

## 8. 저장소 구조

```text
Carrot-comma-SIM/
├─ carrot_sim/
│  ├─ h1_evidence.py              # schema-v6 H1 trace/config strict parser + identity 검증
│  ├─ h1_evidence_set.py          # H1_READY / H1_HOLD qualification
│  ├─ h1_jsonl.py                 # normalized JSONL ingestion boundary
│  ├─ openpilot_overlay_compat.py # upstream H1 host-surface 호환성 검사
│  ├─ simulator_contract.py       # World / Plant / state / safety contract
│  ├─ vehicle_plant_axes.py       # Lateral + Longitudinal 조합 및 차량 wrapper
│  ├─ simulator_loop.py           # Fail-closed closed-loop 실행기
│  └─ scenario_test_catalog.py    # 시나리오 정의 및 우선순위
├─ examples/
│  ├─ basic_closed_loop.py
│  ├─ h1_evidence_ready.jsonl
│  └─ h1_evidence_missing_config.jsonl
├─ integration/openpilot/
│  └─ h1_overlay_manifest.json    # live overlay 최소 허용 경계
├─ scripts/
│  ├─ inspect_h1_evidence.py
│  └─ check_openpilot_overlay.py
├─ tests/
├─ docs/
│  ├─ PROJECT_STATUS_KO.md
│  ├─ H1_OBSERVABILITY_KO.md
│  ├─ ARCHITECTURE_KO.md
│  └─ VEHICLE_PLUGIN_GUIDE_KO.md
└─ README_EN.md
```

---

## 9. 다른 차량을 추가하는 기본 절차

```text
새 차량 로그 확보
      ↓
차량 ID / 코드 / 설정 provenance 확인
      ↓
Lateral 입력-반응 식별
      ↓
Longitudinal 입력-반응 식별
      ↓
차량별 Validated Domain 정의
      ↓
독립 로그 검증
      ↓
Vehicle Plugin 등록
      ↓
공통 Closed-loop / Scenario 엔진 사용
```

단순히 차량 이름만 바꿔서 "지원"으로 표시하지 않습니다. **차량별 증거와 검증이 있어야 해당 차량의 validated plugin으로 취급**하는 것이 원칙입니다.

---

## 10. 로드맵

- [x] World와 Vehicle Plant 분리
- [x] 범용 `CombinedVehiclePlant`
- [x] Santa Fe strict reference wrapper
- [x] Fail-closed simulation contract
- [x] 결정론적 scenario catalog
- [x] schema-v6 H1 evidence strict parser / structural qualification
- [x] eGPU/통합 브랜치를 simulator 필수 경로에서 분리
- [ ] 실제 comma read-only inventory 및 기존 H1 overlay 분류
- [ ] 실제 comma H1 evidence 확보 및 controller replay fidelity 검증
- [ ] Santa Fe longitudinal Plant 검증 완료
- [ ] 실제 Carrot/openpilot controller bridge 공개판 정리
- [ ] 표준 Vehicle Profile / Plugin 포맷 확정
- [ ] 두 번째 차량으로 재현성 검증
- [ ] MetaDrive/SUMO/CommonRoad 계열 World adapter 확대
- [ ] 자동 regression / scenario coverage dashboard

---

## 11. 공개판 개인정보 정책

이 저장소에는 다음 정보를 올리지 않습니다.

- 원본 `rlog` / `qlog` 및 차량 영상
- 실제 route ID
- comma 장치 hostname/IP
- SSH key 또는 key 경로
- 개인 PC의 절대 경로
- 개인 장치 ID
- 위치를 역추적할 수 있는 원본 주행 메타데이터

공개 가능한 synthetic/example 데이터와 익명화된 통계만 사용합니다.

---

## 12. Carrot / openpilot과의 관계

이 저장소는 Carrot/openpilot 계열 제어기를 연구하기 위한 **독립적인 시뮬레이터 프로젝트**입니다. 현재 공개판에는 openpilot 또는 Carrot의 전체 소스 트리를 vendoring하지 않습니다. 외부 프로젝트의 상표·코드·라이선스는 각 upstream 프로젝트에 귀속됩니다.

Carrot-WIP의 일반 업데이트를 이 프로젝트가 승인하거나 차단하지 않습니다. 우리가 유지하는 것은 replay에 필요한 최소 H1 observability overlay와 그 호환성 검사입니다. eGPU 연구 브랜치/Guardian/model-slot/telemetry/commissioning은 이 시뮬레이터의 필수 dependency가 아닙니다.

현재 저장소 자체 코드의 재배포 라이선스는 별도로 정리할 예정입니다. 단순히 GitHub 저장소가 public이라는 사실만으로 별도의 사용 권한이 자동 부여되는 것은 아닙니다.

---

## 13. 프로젝트가 지향하는 최종 형태

```text
                     Carrot / openpilot
                            │
                    Common Controller API
                            │
                    CombinedVehiclePlant
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
       SantaFe Plugin   Vehicle B      Vehicle C
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                     Scenario Engine
                            ▼
                  Automated Evaluation
                            ▼
              Regression / Coverage Report
```

**싼타페 한 대를 흉내 내는 프로그램이 아니라, 실제 주행 증거를 기반으로 여러 차량의 응답 모델을 추가할 수 있는 Carrot/openpilot용 범용 시뮬레이션 구조**가 최종 목표입니다.
