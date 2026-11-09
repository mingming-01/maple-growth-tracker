# P5-3. React 스타일·상태·API 경계 정리

> 기준 브랜치: `chore/p5-1-legacy-dependency-audit-20261109`
> 목적: React 화면이 레거시 전역 스타일에 의존하지 않도록 분리하고, React의 HTTP 요청 진입점을 서비스 계층으로 모은다.

## 1. CSS 경계

- `frontend/index.html`에서 `/static/style.css` 참조를 제거했다.
- React 진입점은 `frontend/src/main.jsx`에서 `frontend/src/styles.css`만 import한다.
- 기존 스타일 중 React 컴포넌트가 실제 사용하는 규칙은 React 스타일시트로 이전했다.
- 이전 대상은 캐릭터 상세 정보, 성장 타임라인·목표, 기간 요약, AI 분석 상태 등 React JSX에서 참조하는 기존 클래스다.
- `templates/index.html`은 계속 `/static/style.css`를 사용하므로 `/legacy/`의 화면 스타일은 유지된다.
- `static/style.css` 자체는 P5-4에서 레거시 화면 종료를 결정하기 전까지 삭제하지 않는다.

## 2. API 경계

- `frontend/src/services/api.js`에 공통 transport 함수 `requestResponse`를 두어 JSON API와 HTML 기반 관리자 인증 요청이 동일한 same-origin 요청 정책을 사용하도록 했다.
- 관리자 로그 조회(`getAdminLogs`), 로그인(`loginAdmin`), 로그아웃(`logoutAdmin`)을 서비스 계층으로 이동했다.
- `AdminDashboard.jsx`에서 직접 `fetch`를 호출하던 코드를 제거하고 서비스 함수를 사용하도록 변경했다.
- 관리자 로그인은 기존 Flask 세션과 CSRF 토큰 흐름을 유지한다. 인증 방식이나 서버 API 계약은 변경하지 않았다.
- `requestJson`의 `signal`, `method`, `body`, `cache` 등 호출 옵션 전달을 유지한다.

## 3. 브라우저 저장 상태

- 세션/로컬 저장소 접근은 기존 `frontend/src/lib/storage.js`의 함수로 유지한다.
- React 컴포넌트에서 저장 키나 직렬화 로직을 중복 구현하지 않는다.
- 기존 저장 키와 데이터 구조를 변경하지 않았으므로 별도 데이터 마이그레이션은 수행하지 않았다.

## 4. 회귀 검증

- React 루트 진입 문서에 레거시 `/static/style.css` 링크가 포함되지 않는지 E2E 검증을 추가했다.
- `/legacy/` 문서에는 기존 `/static/style.css`가 계속 연결되는지 검증을 추가했다.
- 기존 React 관리자 로그 조회·필터 E2E 및 Python 관리자 API 인증 테스트를 유지한다.
- 이번 변경 이후의 전체 CI 결과는 GitHub Actions 완료 후 별도로 확인한다.

## 5. P5-3 판정

CSS와 API의 프런트엔드 경계를 분리했다. 레거시 스타일시트와 레거시 API/DOM 코드는 아직 `/legacy/`에서 사용되므로 삭제하지 않는다. P5-4에서는 React 단독 운영을 전제로 레거시 진입 경로와 참조 코드를 제거하고, P5-5에서 최종 회귀 및 배포를 검증한다.
