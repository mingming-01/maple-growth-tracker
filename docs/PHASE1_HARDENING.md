# Phase 1 운영 안정성 보강

이 문서는 `improve/phase1-hardening`에서 적용한 운영 보호 정책과 제한 범위를 설명한다.

## API 스냅샷 저장

- `GROWTH_DATABASE_URL`이 PostgreSQL URL이면 `api_snapshots` 테이블을 PostgreSQL에 생성하고 저장한다.
- DB 연결에 실패하면 애플리케이션 시작을 막지 않고 SQLite로 폴백하며 관리자 로그 화면에 스냅샷 저장소 경고를 표시한다.
- `GROWTH_DATABASE_URL`이 비어 있으면 로컬 개발용 SQLite를 사용한다.
- 장기 성장 기록과 API 스냅샷은 같은 PostgreSQL 연결 설정을 공유한다.

## Nexon API 요청 제어

- 모든 Nexon 요청과 재시도 시도에 `NEXON_API_MIN_INTERVAL` 간격 제어를 적용한다.
- 기본값은 0.22초다.
- 기존 연결/응답 타임아웃, 제한 응답 재시도 및 지수 백오프를 유지한다.
- 요청 카운트는 앱 인스턴스의 메모리에서 관찰한다. 분산 인스턴스 전체에 걸친 전역 제한이나 외부 API 사업자 측 할당량을 대체하지 않는다.

## AI 요청 한도

| 환경 변수 | 기본값 | 의미 |
|---|---:|---|
| `AI_MAX_REQUESTS_PER_MINUTE` | 5 | IP별 분당 요청 상한 |
| `AI_MAX_REQUESTS_PER_DAY_PER_IP` | 20 | IP별 KST 일일 요청 상한 |
| `AI_MAX_REQUESTS_PER_DAY_GLOBAL` | 100 | 앱 인스턴스별 KST 일일 총 요청 상한 |

한도를 초과하면 HTTP 429와 `Retry-After`를 반환한다. 카운터는 프로세스 메모리에 저장되므로 재시작·다중 인스턴스 환경에서 누적 사용량이 유지되지는 않는다. 따라서 이 기능은 앱 레벨의 남용 방어이지, 실제 금액 기준의 과금 상한이 아니다. 금액 한도는 Gemini/OpenRouter 계정의 공급자 측 예산·알림·키 제한도 함께 설정해야 한다.

## 관리자 로그인 방어

- 기본 5회 실패, 15분 관찰 창, 15분 IP 잠금을 적용한다.
- 운영 환경(`RENDER=true` 또는 `FLASK_ENV=production`)에서는 `ADMIN_PASSWORD_HASH`가 필요하고 평문 `ADMIN_PASSWORD` 대체 인증은 사용하지 않는다.
- 운영 환경에서 세션 쿠키의 Secure 속성을 자동 활성화한다.
- `FLASK_SECRET_KEY`가 누락되거나 너무 짧으면 애플리케이션 시작 시 경고한다. 운영 환경에는 32자 이상의 고정 비밀키를 설정해야 한다.

## 브라우저 테스트

- Playwright 기반 E2E 테스트는 메인 화면 렌더링·빈 검색 검증과 관리자 로그 비인증 접근 차단을 확인한다.
- Nexon/Gemini 실 API에 의존하는 테스트는 아니므로 API 제공자 장애나 실계정 데이터까지 검증하지 않는다.
