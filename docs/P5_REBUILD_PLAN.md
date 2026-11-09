# P5 React 전환 후속 정리 계획

> 기준 브랜치: `main`
> 기준 커밋: `c122ba42cce30c5a9f2ab19f2c65045ea1f11020`
> 작업 브랜치: `refactor/p5-react-boundary-cleanup-20261109`
> 목적: PR #64의 유효한 전환 작업을 현재 main의 모듈형 React 구조 위에서 재검토하고 안전하게 완성한다.

## 기준선

- PR #63에서 도입한 기능별 React 컴포넌트 구조를 유지한다.
- PR #65에서 복원한 최고 관측 전투력, AI 분석 근거 데이터, 관리자 API 서비스 경계를 유지한다.
- PR #64의 이전 브랜치는 병합하거나 복구하지 않는다.
- 현재 main은 React 빌드가 존재하면 `/`에서 React를 제공하고, 빌드가 없으면 레거시 화면으로 폴백한다.
- `/legacy/`와 `/preview/`는 운영 비교·검증 경로로 남아 있다.

## 작업 원칙

1. 삭제보다 의존성 확인과 기능 동등성 검증을 먼저 한다.
2. React 컴포넌트 분리 구조를 단일 대형 컴포넌트로 되돌리지 않는다.
3. Flask API, 관리자 인증, 백엔드 데이터 파일은 프런트엔드 레거시로 오분류하지 않는다.
4. 운영 URL 검증 전에는 레거시 경로, fallback, 기존 화면 자산을 제거하지 않는다.
5. 각 단계에서 테스트를 추가하고 실제 CI 결과를 확인한다.
6. 완료되지 않은 작업은 완료로 표시하지 않는다.

## 단계별 계획

### P5-A. 현재 main 기능 동등성 재점검
- #63/#65 기준 React 기능 및 테스트 현황 확인
- #64의 P5-2 기능 목록과 현재 구현·테스트를 항목별 대조
- 누락 기능만 별도 작업으로 확정
- 성장 계산 파일과 상세 탭 구현은 중복 재작성하지 않고 기존 테스트를 기준으로 검증

### P5-A 점검 결과 (2026-11-09)

- React 진입은 `frontend/src/main.jsx` → `App.jsx`이며, #63의 기능별 컴포넌트 구조가 유지된다.
- 화면 구성은 `GrowthHome.jsx`가 개요·성장·상세·AI·날짜별 기록·비교 화면을 연결하고, 캐릭터 상세는 스탯·장비·심볼·6차 스킬·링크·유니온 탭을 별도 컴포넌트로 분리한다.
- 확인된 주요 기능: 캐릭터 조회/갱신, 관심 캐릭터, 성장 분석·목표·타임라인, 상세 정보, AI 리포트/근거 데이터, 날짜별 기록, 캐릭터 비교, 관리자 로그, 이미지/PDF 내보내기.
- #65의 최고 관측 전투력 및 관측일 저장, AI 근거 카드/캐시 복원, 관리자 API 서비스 연결이 현재 main 코드에 존재한다.
- React E2E는 `e2e/react-preview.spec.cjs` 9개와 `e2e/character-details.spec.cjs` 1개다. `e2e/app.spec.cjs` 7개는 `/legacy/`를 대상으로 하므로 React 기능 검증으로 계산하지 않는다.
- `tests/test_preview_route.py`는 React 빌드 부재 시 루트가 레거시로 폴백하는 동작을 명시적으로 검증한다. 이는 운영 전환 전 현재 동작이므로 임의 제거하지 않는다.
- `frontend/src/App.jsx`에는 직접 API fetch가 없고, 관리자 API는 `services/api.js`를 사용한다. 저장소 접근도 `lib/storage.js`에 모여 있다.
- React JSX에서 사용하는 일부 클래스가 `static/style.css`에만 정의돼 있었다. PR #64의 React CSS 이전 변경에서 현재 사용 중인 공통·상세 UI 규칙을 선별해 `frontend/src/styles/react-compat.css`로 이식하고, React 진입 HTML의 레거시 stylesheet 링크를 제거한다. 레거시 Flask 템플릿은 기존 `static/style.css`를 계속 사용한다.
- CSS 클래스명 대조는 정적 분석이므로 동적 클래스명과 전역 규칙은 E2E 및 브라우저 계산 스타일 검증으로 보완한다.
- `GrowthDashboard.jsx`(734줄), `AnalyticsAndComparison.jsx`(484줄)는 기능 파일로 분리돼 있으나 내부 책임이 크다. P5-A에서는 재분리하지 않고, 테스트와 책임 경계를 확인한 뒤 후속 대상으로 판단한다.

### P5-A 판정

기능 구조와 주요 기능은 현재 main에 유지되고 있다. 다만 React 전용 E2E가 성장 목표·타임라인·세부 기능 전반을 모두 독립 검증하는 수준은 아니므로, P5-B와 병행해 테스트 공백을 보완한다. **P5-A 코드 기능 동등성 확인은 완료, 전체 테스트 커버리지 동등성은 미완료**로 기록한다.

### P5-B. React 스타일 경계 분리
- 현재 `frontend/index.html`이 `/static/style.css`를 로드하는 이유를 실제 React JSX 및 관리자 템플릿 참조와 대조
- React 화면이 사용하는 규칙만 React 전용 스타일로 이전
- 기존 `static/style.css`는 레거시 사용자 화면 및 Flask 관리자 템플릿의 사용처가 남아 있으면 유지
- React 문서에서 레거시 전역 스타일 의존성이 제거됐는지 테스트

### P5-B 진행 내용

- `frontend/src/styles/react-compat.css`를 추가해 React에서 사용하는 공통 로딩/오류, 성장 목표·타임라인, 기간 요약, 상세 장비·스탯·유니온 UI 규칙을 React 번들에 포함한다.
- `frontend/src/main.jsx`에서 React 호환 스타일을 명시적으로 import한다.
- `frontend/index.html`의 `/static/style.css` 링크를 제거한다. `/legacy/` 및 Flask 관리자 템플릿의 링크는 변경하지 않는다.
- React 루트 E2E에서 레거시 CSS 링크 부재와 React CSS 번들의 핵심 규칙 포함을 검증하도록 보강한다.

### P5-C. API·상태 경계 검증
- 관리자 API 호출이 `frontend/src/services/api.js`에 모였는지 확인
- 브라우저 저장소 접근이 `frontend/src/lib/storage.js` 경계를 따르는지 확인
- Flask 세션·CSRF·API 계약은 불필요하게 변경하지 않음

### P5-D. 레거시 퇴역 사전 조건
- Render 운영 URL에서 React 루트 화면과 주요 기능을 확인
- 관리자 로그인·로그 화면 및 정적 자산 확인
- 빌드 실패 시 복구 방법과 fallback 제거의 운영 영향을 검토
- 위 조건이 충족되기 전에는 `/legacy/`, `/preview/`, fallback, 기존 JS/템플릿을 제거하지 않음

### P5-E. 레거시 퇴역 및 최종 회귀
- P5-D 승인 후 제거 가능한 라우트·템플릿·JS만 개별 제거
- Python 단위 테스트, JavaScript 테스트, React 빌드, Playwright E2E 실행
- 실제 운영 배포를 별도로 확인하고 CI 성공과 혼동하지 않음

## 현재 확인된 주의 사항

- `frontend/index.html`은 현재 `/static/style.css`를 직접 로드한다.
- `static/style.css`는 레거시 템플릿뿐 아니라 Flask 관리자 화면에서도 사용될 수 있으므로 파일 전체 삭제는 금지한다.
- `static/jobs.json`은 Python Nexon 서비스의 직업 매핑 데이터이므로 프런트엔드 정리 대상이 아니다.
- 현재 main의 `tracker/controller/page_controller.py`는 `/`, `/legacy/`, `/preview/` 경로를 유지하며, React 빌드가 없을 때 루트에서 레거시 템플릿으로 폴백한다.

## 완료 기준

- 각 작업이 현재 main의 실제 코드와 연결되어 있음이 확인될 것
- 변경한 기능에 회귀 테스트가 존재할 것
- 관련 CI가 성공할 것
- 레거시 삭제는 운영 검증과 복구 계획이 확인된 후에만 수행할 것
