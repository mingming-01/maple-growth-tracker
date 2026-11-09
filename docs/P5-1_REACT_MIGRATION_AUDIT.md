# P5-1. React 전환 대상 및 레거시 의존성 조사

> 기준 브랜치: `main`
> 조사 기준일: 2026-11-09
> 목적: 기존 구현을 무조건 보존하는 것이 아니라, 기능 책임을 React 또는 Flask로 이전한 뒤 기존 구현을 제거하기 위한 사전 조사
> 범위: 저장소에서 확인한 프런트엔드 진입점, 화면 템플릿, API 클라이언트, 성장 계산, 캐릭터 상세, 공통 스타일 및 직업 매핑

## 1. 현재 진입 경로 확인

| URL | 현재 동작 | 확인된 구현 |
|---|---|---|
| `/` | React 빌드 산출물 `static/react-preview/index.html`이 있으면 React를 제공하고, 없으면 기존 템플릿으로 폴백 | `tracker/controller/page_controller.py::home` |
| `/legacy/` | 기존 템플릿을 항상 제공 | `legacy_home` → `templates/index.html` |
| `/preview/` | React 빌드가 있으면 React 제공, 없으면 503 안내 페이지 | `react_preview` → `templates/react_preview_unavailable.html` |
| `/preview/<asset>` | React 빌드 산출물의 상대 경로 자산 제공 | `react_preview_asset` |

**중요:** React가 정상 표시되는 것만으로 레거시 코드가 사용되지 않는다고 판단할 수 없다. 운영 빌드가 존재하는 경우 `/`는 React지만, `/legacy/`는 의도적으로 기존 화면을 제공하며, React 빌드 산출물이 없을 때 `/`도 기존 화면으로 폴백한다.

## 2. 확인된 코드 연결 관계

### React 경로

- `frontend/index.html`이 `#root`와 `/src/main.jsx`를 제공한다.
- `frontend/src/main.jsx`가 React root를 만들고 `App.jsx`, `frontend/src/styles.css`를 불러온다.
- `frontend/src/App.jsx`는 `frontend/src/services/api.js`, `frontend/src/lib/storage.js`, `frontend/src/lib/growth.js`, 캐릭터 상세·성장 대시보드·AI 분석 컴포넌트를 사용한다.
- React API 요청은 `frontend/src/services/api.js`의 `requestJson` 및 기능별 API 함수가 담당한다.
- 다만 `frontend/index.html`은 별도로 `/static/style.css`도 링크한다. 따라서 이 CSS는 React 화면에서도 로드되는 현재 공유 자원이다.

### 레거시 경로

- `templates/index.html`은 기존 DOM 기반 화면을 정의하고 마지막에 `/static/app.js`를 module script로 로드한다.
- `static/app.js`는 `static/js/api.js`, `static/js/character-details.js`, `static/js/growth.js`를 import한다.
- 기존 화면의 API 처리, DOM 렌더링, 캐릭터 상세 UI 및 성장 계산은 이 모듈들에 연결되어 있다.
- 따라서 위 JS 파일들은 `/legacy/`와 React 빌드 부재 시의 폴백 화면에서 실제로 필요한 코드다. 지금 바로 삭제하면 기존 경로가 깨진다.

## 3. 파일별 1차 분류

| 파일 / 영역 | 현재 확인된 역할 | 1차 판정 | 전환 방향 |
|---|---|---|---|
| `static/app.js` | 레거시 화면의 DOM 이벤트·렌더링 진입점 | React 이전 후 제거 후보 | React 화면 기능과 대조해 미이전 기능을 이전 |
| `static/js/api.js` | 레거시 화면의 fetch/응답 처리 | 중복 구현 | React API 클라이언트로 기능 통합 후 제거 후보 |
| `static/js/character-details.js` | 레거시 캐릭터 상세 DOM 생성 | React 대체 구현 존재 | React 상세 컴포넌트와 API·탭·상태 기능을 항목별 대조 |
| `static/js/growth.js` | 레거시 성장 지표 계산 | React 계산 모듈 존재 | 계산 결과와 경계 조건 테스트를 맞춘 뒤 제거 또는 서버 도메인으로 통합 |
| `templates/index.html` | 레거시 전체 화면 및 fallback | 전환 후 제거 후보 | React를 기본 진입으로 확정하고 fallback 정책 종료 |
| `templates/react_preview_unavailable.html` | React 빌드가 없을 때 미리보기 안내 | 임시 운영 보조 | `/preview/` 폐지 또는 개발 전용 경로 유지 여부 결정 |
| `static/style.css` | 기존 화면 스타일이며 React 진입 HTML에서도 링크 | 공유 중 / 혼합 가능성 | React에서 사용하는 규칙을 식별해 `frontend/src/styles.css` 또는 전용 스타일로 이전한 뒤 레거시 규칙 제거 |
| `frontend/src/styles.css` | React 전용 스타일 | 유지 | React 디자인 시스템의 기준으로 정리 |
| `frontend/src/services/api.js` | React API 요청·응답 처리 | 유지 및 통합 기준 | React API 클라이언트의 단일 진입점으로 유지 |
| `frontend/src/lib/growth.js` | React 성장 계산 | 유지 및 대조 기준 | 기존 JS 계산과 테스트 결과를 비교 |
| `static/jobs.json` | `tracker/services/nexon_service.py`가 동적으로 경로를 구성해 읽는 직업 API 매핑 | 백엔드 의존성, 프런트 레거시 아님 | React 이전 대상에서 제외. 백엔드 데이터로 유지할지 별도 검토 |
| `static/images/worlds/*` | 기존 화면과 React의 월드 이미지 경로에서 사용 | 공유 자산 | 참조 경로 통합 후 유지 |
| `static/favicon.svg` | React HTML과 레거시 템플릿에서 사용 | 공유 자산 | 공통 정적 자산으로 유지 |

## 4. 핵심 판단

1. **React 화면은 별도 구현으로 이미 존재한다.** 따라서 P5는 React를 처음부터 다시 만드는 작업이 아니라, 기존 화면에 남아 있는 기능과 공유 의존성을 대조하고 React 쪽으로 책임을 옮기는 작업이다.
2. **레거시 JS 3개 모듈은 현재 삭제할 수 없다.** `/legacy/` 및 빌드 부재 fallback에서 호출된다. 다만 이는 영구 유지 근거가 아니라 이전 완료 전까지의 의존성이다.
3. **API 클라이언트와 성장 계산은 중복 구현 가능성이 확인된다.** 레거시 `static/js/api.js` ↔ React `frontend/src/services/api.js`, 레거시 `static/js/growth.js` ↔ React `frontend/src/lib/growth.js`를 기능별로 비교해야 한다.
4. **스타일은 단순 삭제 대상이 아니다.** React HTML이 `/static/style.css`를 직접 링크하므로, React에서 실제 사용하는 선택자와 자산을 먼저 분리해야 한다.
5. **`static/jobs.json`은 프런트엔드 레거시가 아니다.** Python 서비스에서 읽으므로 React로 이동시키지 않는다.
6. **서버 라우팅도 레거시 제거의 일부다.** React 전환 완료 후 `/legacy/`, fallback 및 `/preview/` 정책을 함께 정리해야 한다.

## 5. P5-2 진입 전 추가 확인 항목

이번 1차 조사는 진입점과 주요 모듈의 직접 연결을 확인한 결과다. GitHub 코드 검색 결과가 이 저장소의 검색 결과를 반환하지 않아, 저장소 전체의 모든 문자열 참조를 검색으로 증명하지는 못했다. 따라서 아래 항목은 확인 전까지 삭제 가능으로 간주하지 않는다.

- [ ] `static/app.js`의 기능 목록을 React App 및 각 feature와 대조해 누락 기능 확인
- [ ] `static/js/character-details.js`와 React `CharacterDetails`의 탭·프리셋·로딩·오류 처리 비교
- [ ] `static/js/growth.js`와 `frontend/src/lib/growth.js`의 함수별 입력·출력·경계 조건 비교 및 테스트 대조
- [ ] `static/style.css`의 React 사용 선택자와 레거시 전용 선택자 분리
- [ ] `static/images` 전체 참조를 React·레거시·백엔드별로 분류
- [ ] `/admin` 화면과 관리자 API가 React 경로에서 정상적으로 연결되는지 확인
- [ ] 테스트·배포 워크플로가 React 빌드 산출물을 생성하고 제공하는지 확인
- [ ] 직접 URL 진입, 새로고침, 뒤로 가기, 빌드 산출물 부재 시 동작을 검증

## 6. P5-2 실행 원칙

- 기존 코드가 참조된다는 이유만으로 작업을 중단하지 않는다.
- 참조된 기능은 React 또는 Flask의 올바른 책임 위치로 이전한다.
- 대체 구현의 기능 동등성과 테스트를 확인한 후 기존 참조를 끊는다.
- 참조가 끊기고 회귀 테스트가 통과한 파일만 제거한다.
- 백엔드에서 사용하는 데이터·자산은 프런트엔드 이전 대상으로 오분류하지 않는다.
- 이 문서의 판정은 조사 결과에 따라 갱신하며, 확인되지 않은 항목을 '미사용'으로 단정하지 않는다.
