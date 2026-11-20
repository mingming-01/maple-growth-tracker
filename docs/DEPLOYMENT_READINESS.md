# Render 배포 전 운영 점검

> 점검 기준: 2026-11-20. 이 문서는 해당 시점에 조회한 Render 서비스 설정과 로그, 작업 브랜치의 코드·CI를 구분해 기록한다. 운영 설정을 변경하거나 배포한 기록은 아니다.

## 확인된 Render 서비스 구성

| 항목 | 확인값 |
| --- | --- |
| 서비스 | \`maple-growth-tracker\` |
| 배포 브랜치 | \`main\` |
| 마지막 확인 배포 커밋 | \`cdf06d6\` |
| 인스턴스 수 | 1 |
| 플랜 | Free |
| 리전 | Virginia |
| Start Command | \`gunicorn app:app\` |
| 워커 설정 | Render가 \`WEB_CONCURRENCY=1\`을 설정 |
| 워커 유형 | \`sync\` |

Render 계정에서 관리되는 PostgreSQL 인스턴스는 조회되지 않았다. 애플리케이션의 \`GROWTH_DATABASE_URL\`이 Supabase 등 외부 PostgreSQL을 가리키는지는 Render 환경변수 화면에서 연결 문자열의 호스트만 확인해야 한다. 비밀번호와 전체 연결 문자열은 로그나 이 문서에 남기지 않는다.

## Gunicorn 타임아웃

운영 중인 배포 커밋 \`cdf06d6\`의 \`gunicorn.conf.py\`는 \`timeout = 40\`이었다. 2026-11-19 운영 로그에는 AI 분석 요청 도중 다음 기록이 확인됐다.

- \`WORKER TIMEOUT\`
- 동기식 워커가 요청을 처리하다 종료됨
- 해당 요청은 Gemini 503 이후 OpenRouter 무료 라우팅 응답의 출력 길이 제한을 겪은 시점에 발생

작업 브랜치에서는 \`gunicorn.conf.py\`를 120초로 조정했다. Render 대시보드의 Start Command는 Procfile보다 우선하는 \`gunicorn app:app\`이지만, Gunicorn은 작업 디렉터리의 기본 설정 파일 \`./gunicorn.conf.py\`를 읽는다. 따라서 실제 명령과 같은 \`gunicorn app:app\` 실행 경로를 \`--print-config\`로 확인하는 회귀 테스트를 추가했다.

배포 승인 전 확인:
- [ ] 최신 브랜치 CI에서 Gunicorn 유효 타임아웃 120초 테스트 통과
- [ ] Render가 배포할 커밋에 \`gunicorn.conf.py: timeout = 120\` 포함
- [ ] 배포 후 시작 로그와 AI 요청 로그에서 워커 타임아웃 재발 여부 확인

## PostgreSQL 연결 풀의 이론상 상한

연결 풀은 Gunicorn 프로세스별로 생성된다. 현재 코드의 연결 풀 키를 기준으로 기본 튜플 행 형식 저장소는 하나의 풀을 공유하고, 관리자 로그의 \`dict_row\` 저장소는 별도 풀을 사용한다.

- 기본 저장소 풀: \`max_size=4\`
- 관리자 로그 풀: \`max_size=4\`
- 프로세스당 이론상 최대: 8개 연결
- 현재 Render 구성의 워커 수: 1
- 현재 Render 인스턴스 수: 1
- 현재 구성의 이론상 총 상한: 8개 연결

이는 실제 사용량이 아니라 풀 설정에서 계산한 상한이다. 실제로 항상 8개 연결을 여는 것은 아니다. 인스턴스나 워커를 늘리면 상한도 프로세스 수만큼 증가한다.

배포 승인 전 확인:
- [x] `GROWTH_DATABASE_URL`은 Supabase Shared Pooler Session Mode로 확인됨(호스트 `aws-0-us-east-1.pooler.supabase.com`, 포트 `5432`; 자격 증명은 기록하지 않음)
- [x] Supabase Free 프로젝트의 `max_connections=60`, reserved 3, 현재 관측 연결 8개를 읽기 전용으로 확인함. 비예약 57개는 앱 전용이 아니라 Supabase 내부 서비스와 공유하는 슬롯임
- [ ] 예상 워커·인스턴스 수를 곱한 뒤 여유 연결 수 확보
- [ ] 필요할 때만 풀 크기를 조정하고 PostgreSQL 통합 테스트 재실행

## Supabase 연결 방식 확인

`GROWTH_DATABASE_URL`의 호스트와 포트만 확인한 결과, 현재 연결은 Supabase Shared Pooler의 Session Mode다(포트 `5432`). 전체 연결 문자열이나 비밀번호는 저장하지 않는다.

- 애플리케이션은 `psycopg_pool`을 사용하며 프로세스별 풀 상한은 기본 풀 4개와 관리자 로그 풀 4개다.
- 풀 생성 시 `prepare_threshold=None`을 지정해 자동 prepared statement 사용을 비활성화한다.
- Session Mode는 연결 세션을 유지하므로 현재 저장소의 트랜잭션 및 연결 컨텍스트 사용 방식과 부합한다.
- 현재 정보만으로 풀 크기나 연결 방식을 변경할 근거는 없다.

## 운영 환경변수 경고

2026-11-19 Render 시작 로그에서 확인된 경고:

1. \`FLASK_SECRET_KEY\` 미설정: 프로세스 재시작 시 세션이 무효화될 수 있다. 운영용 고정 비밀키를 설정해야 한다.
2. \`TRUSTED_PROXY_HOPS=0\`: 프록시 뒤의 클라이언트 IP를 안전하게 식별할 수 없어 IP별 일반 API 제한이 비활성화된다. 실제 프록시 hop 수를 확인하기 전까지 임의의 값을 설정하지 않는다.

운영 환경변수는 대시보드에서 직접 확인한다. 비밀값을 채팅·커밋·로그에 복사하지 않는다. 세션 키 변경은 기존 세션을 무효화할 수 있으므로 변경 시점을 고려한다.

코드 기준 동작도 확인했다(`tracker/application.py`, `tracker/controller/admin_controller.py`, `tracker/services/request_limits.py`).

- `FLASK_SECRET_KEY`: 운영에서 값이 없으면 임의 키로 실행되므로 재시작 후 기존 세션이 유지되지 않는다. 고정된 32자 이상의 비밀값이 필요하다.
- `ADMIN_PASSWORD_HASH`: 운영 관리자 로그인은 해시 값을 사용한다. 개발용 `ADMIN_PASSWORD` 평문 fallback은 운영에서 허용되지 않는다. 값이 없으면 관리자 로그인이 비활성화된다.
- `TRUSTED_PROXY_HOPS`: 운영에서 0이면 `ProxyFix`가 적용되지 않고, 공개 데이터 API의 IP별 요청 제한 함수는 프록시 IP를 사용자 IP로 오인하지 않도록 해당 제한을 우회한다. 실제 프록시 hop 수를 확인한 뒤에만 설정해야 한다.
- 운영 환경에서는 `SESSION_COOKIE_SECURE`가 자동으로 활성화된다.

이 항목들은 설정값 확인과 운영자 결정이 필요한 사항이다. 이 작업에서는 비밀값 생성·등록이나 proxy hop 수 추측을 하지 않았다.

## 범위와 안전장치

- GitHub PR #101의 작업 브랜치에서만 코드·테스트·문서를 변경한다.
- Render 서비스 설정, 환경변수, 운영 DB는 변경하지 않는다.
- PR 병합과 배포는 별도 승인 전까지 수행하지 않는다.
- CI의 PostgreSQL 서비스 컨테이너 테스트는 격리된 테스트 DB만 사용하며 운영 DB와 무관하다.


## 2026-11-20 추가 운영 검증

### Gunicorn 설정 및 CI

- Render의 실제 Start Command `gunicorn app:app`와 동일한 명령으로 `gunicorn --print-config app:app`를 실행하는 회귀 테스트가 통과했다.
- GitHub Actions 커밋 `606d56f`에서 Python 313개 테스트, JavaScript 41개 테스트, Browser E2E 21개 테스트가 모두 통과했다.
- Gunicorn 관련 테스트 3개(`Procfile` 설정, 기본 설정 파일 로딩, AI 요청 제한보다 긴 worker timeout)가 통과했다.
- 따라서 Render Start Command는 변경하지 않아도 프로젝트 기본 설정 파일의 120초 timeout을 적용하는 것으로 검증됐다.

### 최근 Render 관측 결과

2026-11-19 07:57 UTC부터 2026-11-20 07:57 UTC까지 조회했다.

- 앱 로그에서 `FLASK_SECRET_KEY` 미설정 경고 1건, `TRUSTED_PROXY_HOPS=0` 경고 1건을 확인했다.
- 같은 기간 `WORKER TIMEOUT` 문구 검색 결과는 없었다. 이는 해당 문구가 검색된 로그에 없다는 뜻이며, 모든 요청의 정상 완료를 보증하지 않는다.
- `ADMIN_PASSWORD_HASH` 및 `ADMIN_PASSWORD` 문구 검색 결과는 없었다. 환경변수의 실제 존재 여부를 확인한 결과는 아니다.
- Render의 HTTP 요청 수, HTTP 지연 시간, CPU, 메모리, 인스턴스 수 시계열 조회는 모두 데이터가 비어 있었다. 따라서 현재 시점에서 운영 성능의 수치 기준선이나 배포 전후 비교를 만들 수 없다.
- 최근 24시간 Render 이벤트 조회 결과는 비어 있었다.

### 남은 수동 확인

- [ ] Render 대시보드 Environment에서 `FLASK_SECRET_KEY`, `ADMIN_PASSWORD_HASH`, `TRUSTED_PROXY_HOPS`의 **변수명 존재 여부만** 확인한다. 값은 채팅이나 문서에 복사하지 않는다.
- [ ] 프록시 hop 수를 실제 배포 경로에서 확인한 후 `TRUSTED_PROXY_HOPS` 설정을 결정한다.
- [ ] 다음 실제 배포 후 앱 시작 로그에서 Gunicorn 유효 timeout과 세션 키 경고를 재확인한다.
- [ ] Render 메트릭이 수집되는 기간에 HTTP 요청 수·지연 시간·CPU·메모리 기준선을 다시 측정한다.
