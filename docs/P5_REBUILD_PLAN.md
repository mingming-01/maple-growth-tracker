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

### P5-B. React 스타일 경계 분리
- 현재 `frontend/index.html`이 `/static/style.css`를 로드하는 이유를 실제 React JSX 및 관리자 템플릿 참조와 대조
- React 화면이 사용하는 규칙만 React 전용 스타일로 이전
- 기존 `static/style.css`는 레거시 사용자 화면 및 Flask 관리자 템플릿의 사용처가 남아 있으면 유지
- React 문서에서 레거시 전역 스타일 의존성이 제거됐는지 테스트

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
