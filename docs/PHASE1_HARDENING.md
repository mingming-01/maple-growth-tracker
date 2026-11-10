# Phase 1 운영 안정성 보강

이 문서는 `improve/phase1-hardening`에서 적용한 초기 운영 보호 정책과 제한 범위를 정리한 기록입니다. 현재 환경변수 기본값과 동작은 저장소의 `tracker/config.py` 및 관련 서비스 구현을 기준으로 확인하세요.

## API 스냅샷 저장

- `GROWTH_DATABASE_URL`이 PostgreSQL URL이면 `api_snapshots` 테이블을 PostgreSQL에 생성하고 저장한다.
- API 스냅샷 저장소의 PostgreSQL 초기 연결에 실패하면 애플리케이션 시작을 막지 않고 SQLite로 폴백하며 관리자 로그 화면에 저장소 경고를 표시한다.
- `GROWTH_DATABASE_URL`이 비어 있으면 로컬 개발용 SQLite를 사용한다.
- 장기 성장 기록, API 스냅샷, 관리자 로그는 같은 PostgreSQL 연결 설정을 공유한다. 저장소별 장애 처리 정책은 서로 다를 수 있다.

## Nexon API 요청 제어

- 모든 Nexon 요청과 재시도 시도에 `NEXON_API_MIN_INTERVAL` 간격 제어를 적용한다.
- 기본값은 0.22초다.
- 연결·응답 타임아웃, 제한 응답 재시도 및 지수 백오프를 적용한다.
- 외부 API 호출 간격 제어는 런타임 프로세스 상태를 사용한다. Gunicorn 다중 worker·분산 인스턴스 전체의 전역 호출량 제한이나 외부 API 사업자 측 할당량을 대체하지 않는다.

## AI 요청 한도

| 환경 변수 | 기본값 | 의미 |
|---|---:|---|
| `AI_MAX_REQUESTS_PER_MINUTE` | 5 | IP별 분당 요청 상한 |
| `AI_MAX_REQUESTS_PER_DAY_PER_IP` | 20 | IP별 KST 일일 요청 상한 |
| `AI_MAX_REQUESTS_PER_DAY_GLOBAL` | 100 | 앱 인스턴스별 KST 일일 총 요청 상한 |

한도를 초과하면 HTTP 429와 `Retry-After`를 반환한다. AI 요청 카운터는 프로세스 메모리에 저장되므로 재시작·Gunicorn 다중 worker·다중 인스턴스 환경에서 누적 사용량이 공유되지는 않는다. 따라서 이 기능은 앱 레벨의 남용 방어이지, 실제 금액 기준의 과금 상한이 아니다. 금액 한도는 Gemini/OpenRouter 계정의 공급자 측 예산·알림·키 제한도 함께 설정해야 한다.

## 관리자 로그인 방어

- 기본 5회 실패, 15분 관찰 창, 15분 IP 잠금을 적용한다.
- 운영 환경(`RENDER=true` 또는 `FLASK_ENV=production`)에서는 `ADMIN_PASSWORD_HASH`가 필요하고 평문 `ADMIN_PASSWORD` 대체 인증은 사용하지 않는다.
- 운영 환경에서 세션 쿠키의 Secure 속성을 자동 활성화한다.
- `FLASK_SECRET_KEY`가 누락되거나 너무 짧으면 애플리케이션 시작 시 경고한다. 운영 환경에는 32자 이상의 고정 비밀키를 설정해야 한다.

## 현재 테스트 구성

- Python 단위 테스트는 요청 제한, 외부 API 오류 처리, 관리자 인증·로그 저장 등을 검증한다.
- JavaScript 테스트는 성장 계산, 기록 수집 규칙, 브라우저 저장소 및 React 경계 규칙을 확인한다.
- Playwright E2E는 React 기본·미리보기 화면, 레거시 화면 접근, 캐릭터 상세 UI, 전투력 갱신 동기화, 데이터 일관성 및 요청 보호 시나리오를 다룬다.
- 기본 Tests 워크플로는 Python 테스트, React 빌드, 레거시 JavaScript 구문 검사와 JavaScript 테스트를 실행한다. 브라우저 E2E는 별도 Browser E2E 워크플로에서 수동 실행하거나 대상 경로가 변경된 PR에서 실행한다.
- 테스트는 Nexon/Gemini 운영 API와 실제 계정의 전체 동작을 보증하지 않는다. 실제 서비스 상태는 운영 환경에서 별도로 확인해야 한다.
