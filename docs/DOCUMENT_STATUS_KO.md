# Carrot-comma-SIM 문서 상태 인덱스

기준일: 2026-09-10

이 문서는 공개 저장소의 Markdown 문서가 **현재 상태 설명인지, 구조/계약 설명인지**를 빠르게 구분하기 위한 인덱스입니다. 개인 차량의 실제 연식·트림, route, 장치 주소, SSH 정보, 원본 주행로그는 공개 문서에 기록하지 않습니다.

## 현재 상태를 볼 때

다음 순서로 읽습니다.

1. [`README.md`](../README.md) — 프로젝트 목적, 현재 공개 상태, 로드맵
2. [`PROJECT_STATUS_KO.md`](PROJECT_STATUS_KO.md) — 현재 구현/미완료 범위와 다음 게이트
3. [`H1_OBSERVABILITY_KO.md`](H1_OBSERVABILITY_KO.md) — H1 evidence 계약
4. [`H1_ROBUST_ACCEPTANCE_KO.md`](H1_ROBUST_ACCEPTANCE_KO.md) — bounded replay 이후 robust H1 acceptance 방법
4. [`HOW_SIMULATION_OUTPUT_WORKS_KO.md`](HOW_SIMULATION_OUTPUT_WORKS_KO.md) — 설정 → 제어명령 → Plant → 결과 흐름

## 구조와 정책을 볼 때

- [`ARCHITECTURE_KO.md`](ARCHITECTURE_KO.md) — World / Controller / Vehicle Plant 책임 경계
- [`VEHICLE_PLUGIN_GUIDE_KO.md`](VEHICLE_PLUGIN_GUIDE_KO.md) — 차량 플러그인 규칙
- [`SCORING_AND_TUNING_KO.md`](SCORING_AND_TUNING_KO.md) — Safety-related performance / Comfort / Tracking 평가 계약
- [`PUBLIC_PRIVATE_REPO_POLICY_KO.md`](PUBLIC_PRIVATE_REPO_POLICY_KO.md) — 공개 core / private evidence 경계
- [`README_EN.md`](../README_EN.md) — 영문 설명

## Reference Vehicle 표기 원칙

`HYUNDAI_SANTA_FE_2022`는 이 프로젝트에서 사용하는 **openpilot/시뮬레이터의 software reference identity**입니다. 이 식별자만으로 비공개 실제 시험차의 등록연식·트림을 추정하지 않습니다. 실제 차량 identity는 private H0 evidence에서 별도로 확인합니다.

## 현재 공개 경계

- 실제 comma read-only inventory와 offroad H1 host 검증은 수행됐다는 **일반화된 상태만** 공개합니다.
- 실제 장치 주소, hostname, 개인 경로, real settings, rlog/qlog, route provenance는 공개하지 않습니다.
- `H1_READY`는 구조적 evidence 준비 상태입니다. Private evidence의 bounded moving replay PASS도 robust H1 전체 PASS나 실도로 안전성 증명이 아닙니다.
- robust H1은 prospective development A/B + sealed holdout 방식으로 별도 검증합니다.
- 공개 simulator는 실제 차량 Params나 제어값을 자동으로 쓰지 않습니다.

문서 간 설명이 충돌할 경우 이 인덱스보다 `README.md`와 `PROJECT_STATUS_KO.md`의 더 최근 기준일을 우선합니다.
