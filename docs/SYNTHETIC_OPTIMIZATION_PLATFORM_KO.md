# 합성 최적화 플랫폼과 디지털 트윈 UI

이 공개 릴리스는 일반화된 최적화 알고리즘, 합성 데이터, 테스트, 읽기 전용 시각화 UI만 포함한다. 실제 주행 로그·경로 식별자·차량별 허용 범위·실측 점수·채택 이력은 포함하지 않는다.

## 포함 범위

- 결정론적 파라미터 탐색 공간과 제약 조건
- 합성/학습 시나리오 생성 및 폐루프 캠페인 실행
- 신뢰도 기반 후보 판정과 봉인 hold-out 재검증 계약
- 기준/후보 JSONL 재생과 `DIGITAL TWIN · DATA BACKED` UI
- 공개 유출을 막는 fail-closed 감사 스크립트

## 합성 예제 실행

```bash
PYTHONPATH=. python -m carrot_sim.visual_app_server \
  --catalog examples/visual_app_catalog.json --port 8772
```

브라우저에서 `http://127.0.0.1:8772/`를 연다. 서버는 loopback 주소만 허용한다.

예제 카탈로그는 6개의 합성 이벤트를 나타내는 두 개의 3프레임 실행으로 구성된다. `synthetic-baseline`과 `synthetic-candidate`는 설명용 데이터이며 실제 차량 추천 근거가 아니다.

## 안전 경계

UI의 `READ ONLY · 실차 제어 없음`, `실차 쓰기 차단` 표시는 기능 계약이다. 모든 예제의 `recommendation_authorized`와 `real_vehicle_write`는 `false`다.

화면에는 입력 프레임에 실제 lead 데이터가 있을 때만 lead actor가 나타난다. 인접 차선 차량은 데이터가 없으면 만들어내지 않는다. 이 UI는 결과를 관찰하는 도구이며 실제 차량 배포나 설정 변경을 승인하지 않는다.

공개 감사 실행: `python scripts/public_release_audit.py .`
