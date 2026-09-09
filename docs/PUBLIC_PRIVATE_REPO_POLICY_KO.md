# 공개판 / 비공개판 저장소 운영정책

기준일: 2026-09-09

## 1. 목적

Carrot-comma-SIM 프로젝트는 **공개 가능한 범용 시뮬레이터 코어**와 **개인 차량·실주행 evidence를 사용하는 비공개 연구계층**을 분리해 운영합니다.

핵심 원칙은 다음과 같습니다.

```text
Public core
  = 코드 / 계약 / synthetic 예제 / 공개 가능한 문서

Private research layer
  = 실제 차량 설정 / route / raw evidence / 개인 calibration / 튜닝 결과
```

공개판은 비공개 evidence가 없어도 빌드·테스트·예제 실행이 가능해야 합니다.

## 2. 공개판에 둘 수 있는 것

- 범용 simulator core
- H0/H1/H2 데이터 계약과 validator
- Vehicle Plant 인터페이스
- scenario engine 및 deterministic regression
- synthetic/example 데이터
- 공개 가능한 unit/integration tests
- Safety-related performance / Comfort / Tracking 평가정의
- 파라미터 탐색 알고리즘과 점수화 원칙
- 실제 식별정보가 제거된 익명 통계
- 공개 가능한 architecture / plugin / observability 문서

## 3. 공개판에 두면 안 되는 것

- 실제 개인 차량의 현재 Carrot Params 전체 덤프
- 원본 rlog/qlog
- route ID, dongle/device ID
- comma hostname/IP
- 개인 PC 절대경로
- SSH key/token/credential
- 실주행 영상이나 위치를 복원할 수 있는 메타데이터
- 개인 차량별 raw calibration evidence
- 실제 추천 파라미터 후보와 개인 실주행 채택 이력
- 비공개 source provenance를 복원할 수 있는 민감 자료

공개 전에 `public_release_audit`와 수동 리뷰를 모두 거칩니다.

## 4. 비공개 연구판의 역할

비공개 연구판은 공개 코어 위에 개인 evidence 계층을 얹는 곳입니다.

다음 자료는 비공개판에서 관리합니다.

- 실제 주행 로그 intake / reservation / provenance
- 실제 차량별 settings snapshot
- route/segment evidence
- 개인 차량 calibration
- H1/H2 실증 결과
- parameter sweep 원자료
- candidate score와 worst-case 분석
- 실차 검증 결과
- 채택/보류/폐기된 세팅 이력
- device/offroad validation 기록

## 5. 동기화 방향

기본 방향은 **Public → Private**입니다.

```text
Carrot-comma-SIM public main
        ↓
검증된 public core commit 고정
        ↓
private research branch에서 동기화
        ↓
private evidence / calibration / tuning 수행
```

비공개판은 어떤 public core commit을 기준으로 연구했는지 기록해야 합니다.

Private → Public은 자동 동기화하지 않습니다. 공개 후보는 반드시 sanitization과 별도 리뷰를 거칩니다.

## 6. Public core baseline 기록

비공개 연구결과에는 최소한 다음을 함께 기록합니다.

- public repository
- public commit SHA
- private branch/commit
- Carrot upstream commit
- vehicle identity class
- evidence schema version
- parameter/config identity

이렇게 해야 나중에 같은 결과를 어느 코드 기준에서 만든 것인지 추적할 수 있습니다.

## 7. Private → Public 승격 절차

공개 가능한 개선사항을 발견했다고 바로 public에 복사하지 않습니다.

```text
private result
  ↓
개인/route/device 정보 제거
  ↓
실제 차량값을 synthetic/generalized fixture로 대체
  ↓
공개 코어와 독립적으로 재현 가능한지 확인
  ↓
privacy audit
  ↓
PR + CI
  ↓
public main
```

실제 사용자 세팅이나 route evidence를 재현용 예제로 그대로 쓰는 것은 금지합니다.

## 8. 파라미터 추천 데이터의 분리

공개판에는 다음을 둘 수 있습니다.

- metric 정의
- score normalization 방법
- hard-gate 구조
- Pareto/worst-case ranking 원칙
- synthetic candidate 예시

비공개판에는 다음을 둡니다.

- 실제 현재 세팅값
- 실제 차량의 allowed search range
- 실제 candidate 조합
- 실제 route별 score
- 실제 채택 추천값
- 주행 후 feedback와 재보정 결과

## 9. 브랜치 정책

공개판:

- `main`: 공개 source of truth
- review branch는 고유 미검증 변경이 있을 때만 유지
- merge 완료/고유 커밋 없는 작업 브랜치는 정리

비공개판:

- 기본 연구 브랜치는 private evidence source of truth
- 실차/실험별 integration branch는 provenance가 필요할 때 유지
- 오래된 브랜치는 고유 evidence가 없는지 확인한 뒤 정리

## 10. 실패 방지 원칙

- public 저장소에 private 자료가 한 번 push되면 단순 삭제만으로 완전 제거됐다고 가정하지 않습니다.
- 민감자료가 실수로 공개되면 credential rotation 및 Git history 정리 여부를 별도로 검토합니다.
- private evidence를 public test fixture로 직접 사용하지 않습니다.
- public core가 private data path를 하드코딩하지 않습니다.
- private 연구결과가 public acceptance authority를 자동 획득하지 않습니다.

## 11. 현재 운영판정

2026-09-09 기준으로 공개 `Carrot-comma-SIM`과 별도의 private simulator research repository가 실제로 분리되어 있습니다.

다만 공개 코어가 더 빠르게 최신화되고 있으므로, 향후 private 연구를 재개할 때는 **최신 public core baseline SHA를 먼저 기록하고 동기화한 뒤 private evidence 연구를 계속하는 것**을 표준 절차로 사용합니다.
