# 성능 계측 기준

## 목적

P3 성능 개선의 전후를 비교할 수 있도록 서버 프로세스에서 관측 가능한 요청·외부 API·캐시·DB 지표를 수집한다. 계측 데이터는 기능 응답이나 DB 데이터에 영향을 주지 않으며, 각 프로세스 메모리에 제한된 표본만 보관한다.

## 조회

관리자 로그인 후 다음 경로를 조회한다.

- GET /admin/api/performance

React 관리자 세션 인증을 그대로 사용한다. 별도 API 키나 브라우저의 Supabase 접근 권한은 필요하지 않다.

## 지표

| 지표 | 설명 |
|---|---|
| http.requests | Flask endpoint별 요청 수와 HTTP 상태 |
| http.request_ms | Flask endpoint별 처리 시간 |
| cache.lookups | 일반 응답 캐시 및 Nexon 원본 데이터 캐시의 hit/miss |
| cache.writes | 해당 캐시에 새 값을 저장한 횟수 |
| nexon.logical_requests | Nexon API 논리 요청 수 |
| nexon.attempts | 재시도를 포함한 실제 HTTP 시도 수 |
| nexon.retries | 첫 시도 이후 재시도 수 |
| nexon.responses / nexon.errors | 엔드포인트·상태 코드별 응답과 네트워크 오류 |
| nexon.logical_request_ms | 스로틀 대기와 재시도를 포함한 논리 요청 시간 |
| db.connections / db.connection_ms | 저장소별 DB 연결 생성 횟수와 연결 생성 소요 시간 |
| db.operations / db.operation_ms | 성장 기록·스냅샷·관리자 로그 작업 횟수와 처리 시간 |
| db.sql_statements | 계측을 연결한 저장소 작업에서 실행한 SQL 문장 수(일괄 upsert는 행 수 기준) |

각 timing 항목은 표본 수, 최소·최대, 평균, p50, p95를 제공한다. timing 표본은 항목별 최근 2,000개로 제한한다.

## 해석 시 주의

- 계측 시작 시각은 해당 Python 프로세스가 시작된 시각이다. 프로세스 재시작 시 누적 카운터와 표본은 초기화된다.
- 데이터는 프로세스 단위다. Gunicorn worker가 여러 개면 각 worker마다 별도 계측값이 쌓이고, 요청을 처리한 worker의 값만 조회된다. 이 API 응답을 여러 worker의 전역 합계로 해석하면 안 된다.
- Nexon 호출 수는 API endpoint별 논리 요청, 재시도 및 응답을 나눠 계산한다. nexon.attempts를 외부 HTTP 호출 시도 수로 본다.
- Flask endpoint 처리 시간은 백엔드 요청 처리 시간이며, 브라우저 렌더링이나 React의 캐시·상태 복원 시간을 포함하지 않는다. 화면에서 체감하는 검색 전체 시간은 Playwright 또는 브라우저 Performance API 측정을 함께 사용한다.
- DB 연결 시간은 연결 객체 생성 구간을 측정한다. 아직 연결 풀 대기 시간과 연결 생성 시간을 분리한 값은 아니다.
- 본 지표는 성능 비교용 운영 계측의 시작점이며 APM이나 분산 메트릭 저장소가 아니다. 실제 Render/Supabase 수치가 확보되기 전까지 성능 개선 효과를 단정하지 않는다.

## 권장 비교 절차

1. 동일 worker 수와 동일 DB backend에서 프로세스를 재시작해 계측을 초기화한다.
2. 같은 캐릭터·같은 데이터 범위로 캐시 cold 검색을 반복한다.
3. 같은 조건으로 cache warm 검색을 반복한다.
4. 관리자 계정으로 /admin/api/performance 결과를 저장한다.
5. P3 변경 후 동일한 조건으로 다시 측정한다.
6. 검색 p50/p95, endpoint별 Nexon attempts, cache hit/miss 비율, DB connection 수·시간 및 operation 시간을 비교한다.
7. 데이터 정확성, 429 비율, 외부 API 호출량이 악화되지 않았는지도 함께 확인한다.
