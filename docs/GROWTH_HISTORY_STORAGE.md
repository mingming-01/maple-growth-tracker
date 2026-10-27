# 날짜별 성장 기록 저장

## 저장 범위

- 전체 메이플스토리 유저를 수집하지 않는다. 사용자가 검색한 캐릭터만 조회 결과를 저장한다.
- 캐릭터 식별자는 캐릭터명 대신 NEXON API의 `ocid`를 사용하며, 날짜별 기록은 `(ocid, snapshot_date)`를 기본 키로 한다.
- 성공적으로 조회된 경험치·레벨·랭킹은 날짜별로 갱신한다. API가 빈 랭킹 목록을 반환한 날짜는 `not_ready` 상태로 기록하되, 기존 정상 데이터가 이 상태로 덮어써지지 않도록 한다.
- 조회하지 않은 날짜와 API가 데이터를 제공하지 않은 날짜는 구분한다. `not_collected`는 앱이 조회/저장하지 않은 날짜, `not_ready`는 해당 날짜에 API 응답이 비어 있었던 경우다.
- 새 캐릭터를 첫 검색하면 기존 앱 흐름대로 최근 7일의 랭킹을 조회한다. 그중 조회 가능한 기록을 저장하고, 이후 검색할 때마다 새 기록을 누적한다. 예전 기록을 얻을 수 없는 날짜는 임의로 채우지 않는다.

## API 요청량

- 최근 7일 기록은 앱에서 처음 조회할 때 확인한다.
- 저장된 과거 날짜는 다시 API에 요청하지 않고 DB 기록을 재사용한다. 오늘 날짜는 당일 데이터가 나중에 준비될 수 있으므로 다시 확인한다. 어제의 기록이 `not_ready`이면 다음 요청에서 한 번 더 확인한다.
- 30일/90일 보관 기록 조회 API는 DB만 읽으며, 날짜별 넥슨 API 요청을 추가하지 않는다.
- 이는 검색된 캐릭터에 한정한 수집이다. 모든 캐릭터를 주기적으로 순회하거나 백그라운드에서 수집하지 않는다.

## 환경 설정

운영용 PostgreSQL을 연결하려면 Render 웹 서비스의 환경변수에 `GROWTH_DATABASE_URL`을 등록한다. 이 값에는 Supabase 대시보드의 **Connect** 메뉴에서 복사한 PostgreSQL 연결 문자열을 사용한다. 비밀번호가 URL에 포함되므로 소스 코드, README, 로그에 기록하지 않는다.

Render와 연결하는 Supabase 프로젝트에서 IPv4 연결이 필요한 경우 공유 풀러의 **Session mode** 연결 문자열을 사용한다. connection string에서 호스트와 사용자명을 그대로 복사하고, 임의로 조합하지 않는다. 앱은 TLS를 요구한다.

환경변수가 없으면 개발 편의를 위해 `instance/growth_history.sqlite3`를 사용한다. 로컬 개발에서는 기록이 유지되지만, Render의 임시 파일 시스템에서 이를 장기 보관소로 간주하면 안 된다. PostgreSQL 연결이 설정되지 않았다고 해서 실제 영구 저장소가 연결된 것은 아니다.

앱은 PostgreSQL 테이블을 첫 사용 시 생성한다. 동일 스키마를 수동으로 준비하려면 `migrations/20261027_growth_daily_history.sql`을 Supabase SQL Editor에서 실행한다.

## API

- `GET /api/history?name=캐릭터명`: 기존 최근 7일 조회. 성공적으로 얻은 날짜별 기록은 저장소에 저장된다.
- `GET /api/history/archive?ocid=...&days=30`: DB에 저장된 최근 30일 날짜별 기록을 조회한다.
- `GET /api/history/archive?ocid=...&days=90`: DB에 저장된 최근 90일 날짜별 기록을 조회한다.

Archive 응답은 날짜를 모두 포함한다. 기록이 존재하지 않는 날짜는 `recordStatus: "not_collected"`로 표시되고 경험치 값은 비어 있다. 처음 검색한 캐릭터는 과거 날짜 대부분이 비어 있을 수 있다. 데이터가 시간에 따라 쌓이면서 긴 기간의 성장 추이를 볼 수 있다.

## 접근 보안

- 이 테이블은 Flask 서버가 PostgreSQL 연결 문자열로 접근한다. 브라우저에서 Supabase Data API로 직접 조회하지 않는다.
- PostgreSQL 환경에서는 테이블에 RLS를 활성화하고 `PUBLIC`, `anon`, `authenticated` 역할의 직접 권한을 회수한다.
- DB 연결 문자열은 Render의 서버 환경변수에만 보관하고 프런트엔드 코드나 공개 저장소에 넣지 않는다.

## 관리자 로그 보존

- 관리자 운영 로그는 같은 `GROWTH_DATABASE_URL`을 사용해 PostgreSQL의 `action_logs` 테이블에 저장한다.
- 앱 시작 시 테이블과 인덱스를 준비하고, 직접 API 접근을 막기 위해 RLS를 활성화하며 `PUBLIC`, `anon`, `authenticated`의 권한을 회수한다. 브라우저에서 이 테이블에 직접 접근하지 않는다.
- 기록 항목에는 행동, 캐릭터명/월드, 비교 대상, 경로, HTTP 응답 코드, 처리 시간, 제한된 오류 분류가 포함된다. 비밀번호, API 키, 연결 문자열, 요청 본문은 기록하지 않는다.
- DB 연결이 준비되지 않으면 앱의 시작을 막지 않도록 로컬 SQLite로 대체할 수 있지만, 해당 상태는 관리자 로그 화면에 경고로 표시한다. Render에서 SQLite를 장기 보존 저장소로 사용하면 안 된다.
- 기존 `instance/admin_logs.sqlite3`에만 남아 있던 과거 로그는 자동으로 PostgreSQL로 옮겨지지 않는다. 새 저장소 연결 후 발생한 로그부터 영구 보존된다.

## 현재 단계의 한계

- 자동/백그라운드 수집은 구현하지 않았다. 기록은 캐릭터 조회 요청이 있을 때만 갱신된다.
- 기존 SQLite의 일시적 장애 복구 스냅샷과 새 일별 성장 기록 DB는 서로 다른 용도다.
- 실서비스의 영구 저장 여부는 Render에 유효한 `GROWTH_DATABASE_URL`이 설정되어 있고, 해당 PostgreSQL에 연결되는지 확인한 뒤 검증해야 한다.

## 참고

- [Supabase PostgreSQL 연결 가이드](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Render에서 Supabase PostgreSQL 연결하기](https://render.com/articles/how-to-connect-a-render-service-to-supabase-postgres)
