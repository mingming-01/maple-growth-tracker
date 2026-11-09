# P5-4. 레거시 화면 및 진입 경로 퇴역

## 결정

React를 유일한 공개 사용자 화면으로 확정했다. Flask는 API, 외부 연동, AI 서비스, 영속성, 관리자 인증 및 관리자 HTML 화면을 담당한다.

## 변경 사항

- `/`만 공개 사용자 화면으로 유지하고, `static/react-preview/index.html`을 제공한다.
- React 빌드가 없을 때 레거시 템플릿으로 폴백하지 않는다. 배포 설정 누락을 드러내도록 HTTP 503을 반환한다.
- `/legacy`, `/legacy/`, `/preview`, `/preview/`, 미리보기 asset 라우트를 제거했다.
- 레거시 사용자 화면 템플릿 `templates/index.html` 및 미리보기 안내 템플릿을 제거했다.
- 레거시 브라우저 진입점 `static/app.js`, `static/js/api.js`, `static/js/character-details.js`, `static/js/growth.js`를 제거했다.
- 기존 E2E의 레거시 화면 테스트를 React 화면 검증으로 대체했다.
- React E2E는 루트 경로에서 실행하고, 제거된 경로가 404인지 확인한다.
- React AI 분석에서 서버가 반환하는 `growthInsights.basis`, 주간 성장 변화, 주말 성장 비중을 설명하는 근거 카드를 복원했다. 근거는 AI 분석 캐시에 함께 저장·복원한다.
- 관심 캐릭터 저장·복원, 다음 레벨 목표 저장·달성, 모바일 상세 탭 배치를 React E2E로 검증한다.

## 의도적으로 유지한 파일과 자산

| 자산 | 유지 이유 |
|---|---|
| `static/style.css` | Flask 관리자 로그인·로그 HTML 템플릿에서 계속 사용 |
| `templates/admin_login.html`, `templates/admin_logs.html` | 관리자 서버 렌더링 화면 |
| `static/favicon.svg` | React 및 관리자 화면 공용 |
| `static/images/worlds/*` | React 프로필에서 월드 이미지 사용 |
| `static/jobs.json` | Python Nexon 서비스가 읽는 백엔드 매핑 데이터 |
| `static/react-preview/*` | React 빌드 산출물 |

따라서 `static/` 전체 또는 `static/style.css`를 삭제하지 않았다. 관리자 화면의 별도 React 전환은 이 단계 범위가 아니다.

## 운영 및 테스트 계약

- Render Build Command는 `pip install -r requirements.txt && npm --prefix frontend install --no-audit --no-fund && npm --prefix frontend run build`를 실행해야 한다.
- 빌드 산출물이 없으면 `/`는 HTTP 503이다.
- React 브라우저 테스트는 `/`에서 실행한다.
- 관리자 로그인·로그 경로는 기존 Flask 세션과 CSRF 정책을 유지한다.
- 전체 Python, 성장 지표, React 빌드, Playwright E2E CI 결과는 완료 후 확인한다.

## 다음 단계

P5-5에서 전체 회귀 테스트와 실제 배포 사이트의 루트 화면·관리자 경로를 최종 확인한다. 배포 환경 확인은 CI 성공만으로 대체하지 않는다.
