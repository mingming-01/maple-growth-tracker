# P5 — 프런트엔드 레거시 의존성 점검

점검 기준 브랜치: `refactor/p1-growth-home-foundation-20261109`

점검일: 2026-11-09

## 점검 결론

P2~P4에서 React 화면의 실제 사용 경로와 이동 상태를 확인했다. 다만 현재 저장소에는 React 화면 외에도 기존 화면을 제공하는 명시적인 경로와 빌드 실패 시 폴백이 남아 있다.

따라서 이번 P5에서는 **참조가 확인되지 않은 파일만 제거 대상**으로 삼았다. 기존 화면과 연결된 JS/CSS/이미지는 현재도 실행 경로가 있어 제거하지 않는다. React 화면이 준비되었다는 이유만으로 레거시 전체를 삭제하면 안 된다.

## 파일별 의존성 및 조치

| 파일·영역 | 확인된 사용 경로 | 조치 |
|---|---|---|
| `templates/index.html` | `/legacy/`에서 직접 렌더링되고, React 빌드가 없을 때 `/`의 폴백으로 렌더링 | 유지 |
| `static/app.js` | `templates/index.html`에서 모듈 스크립트로 로드 | 유지 |
| `static/js/api.js` | `static/app.js`에서 import | 유지 |
| `static/js/character-details.js` | `static/app.js`에서 import | 유지 |
| `static/js/growth.js` | `static/app.js`에서 import | 유지 |
| `static/style.css` | 레거시 템플릿과 `frontend/index.html` 양쪽에서 로드 | 유지. React 화면의 공통 스타일 의존성이 남아 있음 |
| `static/jobs.json` | `tracker/services/nexon_service.py::_jobs_path()`가 경로를 조합해 열고, `get_api_class()`의 직업 분류 폴백에 사용 | 유지 |
| `static/images/worlds/*` | `static/app.js`의 월드 이미지 매핑에서 사용 | 유지 |
| `static/images/logo.svg`, `static/favicon.svg` | 기존 템플릿에서 사용 | 유지 |
| `templates/react_preview_unavailable.html` | React 빌드가 없을 때 `/preview/`에서 503 안내 화면으로 렌더링 | 유지 |
| `frontend/index.html`, `frontend/src/main.jsx` | Vite 진입점과 React 앱 마운트 | 유지 |
| `frontend/src/styles.css` | React 진입점에서 import | 유지 |
| `frontend/src/features/home/GrowthHome.css` | `GrowthHome.jsx`에서 import | 유지 |
| `frontend/src/components/character/CharacterDetails.css` | `CharacterDetails.jsx`에서 import | 유지 |

## 제거 검토 결과

- `static/jobs.json`은 프런트엔드 코드에서 직접 참조 문자열이 검색되지 않아 미사용 파일 후보로 보였지만, Python 서비스가 `Path`로 경로를 조합해 읽는 간접 의존성이 있었다. 삭제 후 전체 테스트에서 `test_api_class_mapping_is_fallback_in_expected_format`가 실패하는 것을 확인했고, 파일을 즉시 복원했다.
- 기존 화면은 `/legacy/` 경로와 React 빌드 부재 시 루트 폴백으로 실제 제공된다. 기존 화면 스크립트와 스타일을 제거하면 이 경로와 배포 복구 경로가 깨진다.
- `README.md`와 `frontend/README.md`에는 운영 URL에서 React 전환을 검증하고 마이그레이션을 승인하기 전까지 `/legacy/`를 유지하라는 조건이 명시되어 있다. 현재 대화에서는 운영 URL 검증을 수행하지 않았으므로 이 조건은 아직 충족되지 않았다.
- `static/style.css`는 기존 화면 전용 파일로 단정할 수 없다. React 진입 HTML도 이를 로드하므로 React 쪽 공통 스타일 의존성을 별도 이관·검증하지 않고 제거하지 않는다.
- React 컴포넌트 스타일은 각각 실제 진입 컴포넌트에서 import되고 있어 중복 파일로 판단하지 않았다.

## P5 처리 기준

이번 점검에서 안전하게 제거할 수 있다고 입증된 JS/CSS/화면 파일은 확인되지 않았다. 따라서 무리한 삭제는 하지 않았다. 기존 화면을 완전히 폐기하는 작업은 운영 URL에서 React 화면을 검증하고 마이그레이션을 승인한 뒤 진행해야 한다. 전체 회귀 검증(P6)도 완료하기 전에는 `/legacy/`, 루트 폴백, 기존 화면 자산을 제거하지 않는다.
