# P5-2. React 기능 이전 현황 및 동등성 검증

> 기준: P5-1 조사 브랜치의 React 및 레거시 소스
> 목적: 이미 React로 이전된 기능은 재작성하지 않고, 기존 구현과의 연결 및 검증 수준을 명확히 한다.

## 1. 결론

P5-2 조사 결과, 기존 화면의 주요 기능 상당수가 React에 이미 구현되어 있다. 따라서 지금 필요한 작업은 기존 기능을 다시 만드는 것이 아니라, React 구현을 기준 구현으로 확정하고 레거시 경로에 남은 기능 차이를 회귀 테스트로 검증하는 것이다.

## 2. 기능별 대응 관계

| 기존 구현 | React 구현 | 현재 판단 | 후속 조치 |
|---|---|---|---|
| `static/app.js` 캐릭터 조회·프로필 렌더링 | `App.jsx`, `CharacterProfile`, `services/api.js` | React 대응 구현 존재 | 검색·새로고침·오류 상태 테스트 보강 |
| 기존 관심 캐릭터 및 브라우저 저장 상태 | `App.jsx`, `lib/storage.js`, `FavoritesPanel` | React 대응 구현 존재 | 기존 저장 데이터 호환 여부 확인 |
| 기존 성장 통계·그래프·타임라인 | `GrowthDashboard.jsx`, `lib/growth.js` | React 대응 구현 존재 | 계산 결과와 UI 회귀 검증 |
| 기존 목표 레벨·목표일·브라우저 알림 | `GoalPanel` in `GrowthDashboard.jsx` | React 대응 구현 존재 | 저장·수정·삭제·알림 권한 테스트 보강 |
| 기존 AI 기간 분석 | `AIReport` in `AnalyticsAndComparison.jsx` | React 대응 구현 존재 | 30/90일 캐시·수동 재생성 테스트 존재 |
| 기존 캐릭터 비교 및 AI 비교 | `GrowthComparison` in `AnalyticsAndComparison.jsx` | React 대응 구현 존재 | 비교 기간·상태 복원 회귀 검증 |
| 기존 이미지/PDF 저장 | `App.jsx::exportImage/exportPdf` | React 대응 구현 존재 | 실제 파일 저장 브라우저 테스트 보강 |
| 기존 상세 정보 DOM 렌더러 | `CharacterDetails.jsx` 및 상세 탭 컴포넌트 | React로 분할 이전됨 | 6개 탭 로딩 및 오류 테스트 |
| 기존 관리자 링크/로그인·로그 조회 | `AdminDashboard.jsx` | React 대응 구현 존재 | 관리자 API 권한 및 필터 테스트 유지 |
| 기존 API transport `static/js/api.js` | `services/api.js::requestJson` | React 쪽에 독립 구현 존재 | 레거시 화면 퇴역 후 기존 transport 제거 |
| 기존 성장 계산 `static/js/growth.js` | `frontend/src/lib/growth.js` | **두 파일의 blob SHA가 동일** | 레거시 화면 퇴역 후 중복 파일 제거 |

## 3. 확인한 상세 정보 이전 상태

기존 `static/js/character-details.js`는 1,130줄의 DOM 생성·이벤트 처리 모듈이다. React에서는 다음 파일들로 분리되어 있다.

- `CharacterDetails.jsx`: 탭 상태, 지연 로딩, 캐시, 오류·새로고침 처리
- `CharacterDetailsShared.jsx`: 탭 정의, 프리셋, 공통 표시·툴팁
- `CharacterDetailsStats.jsx`: 스탯, 코스메틱, 펫
- `CharacterDetailsEquipment.jsx`: 장비 슬롯 및 잠재 옵션
- `CharacterDetailsOtherTabs.jsx`: 심볼, 6차/HEXA, 링크 스킬, 유니온

React 탭은 스탯·장비·심볼·6차/HEXA·링크 스킬·유니온 총 6개다. 기존 구현의 기능이 모두 동등한지는 API 응답별 시각 검증이 추가로 필요하므로, 파일 분리만으로 완전한 동등성을 단정하지 않는다.

## 4. 기존 E2E 테스트에서 확인된 범위

`e2e/react-preview.spec.cjs`에 이미 존재하는 검증:
- 루트에서 React 제공 및 `/legacy/` 접근 가능
- React 검색·프로필·랭킹·캐릭터 상세 진입
- 이미지/PDF 저장 메뉴 노출
- 관리자 화면 및 로그 필터
- 30일 AI 분석 캐시 재사용 및 수동 재생성
- 모바일 프로필 및 화면 너비

이번 단계에서 추가한 테스트:
- React 캐릭터 상세의 6개 탭이 모두 노출되는지 확인
- 각 탭 선택 시 해당 `section`으로 상세 API 요청이 발생하는지 확인
- 선택한 탭의 `aria-selected` 상태 확인

## 5. 아직 제거하지 않는 이유와 제거 조건

현재 `/legacy/`는 `templates/index.html`을 제공하며, 그 템플릿은 `static/app.js`를 실행한다. React 빌드가 없을 때 `/`도 같은 템플릿으로 폴백한다. 따라서 레거시 JS 파일을 지금 삭제하면 기존 경로와 빌드 부재 fallback이 깨진다.

이는 레거시를 영구 보존하자는 결정이 아니다. 다음 조건을 충족하면 레거시 경로와 파일을 제거한다.

1. React를 유일한 사용자 화면으로 제공할 배포 절차가 확정되어야 한다.
2. React 검색·상세 6개 탭·성장 기록·목표·AI 분석·비교·내보내기·관리자 동작을 회귀 테스트로 검증해야 한다.
3. 저장된 브라우저 상태의 이전 버전 호환 정책을 결정해야 한다.
4. `/`의 fallback 및 `/legacy/`를 종료하고 운영 배포에서 확인해야 한다.
5. 그 후 `static/app.js`, `static/js/*`, 레거시 템플릿과 레거시 전용 CSS를 참조 순서에 따라 제거한다.

## 6. P5-2 판정

- **기능 이전:** 주요 기능은 React에 이미 존재한다. 중복 재작성은 하지 않는다.
- **이번 코드 변경:** 상세 탭 6개의 로딩·선택 상태를 검증하는 E2E 테스트 1건 추가.
- **아직 수행하지 않은 검증:** 테스트 실행 및 실제 브라우저/배포 검증. 이 커밋에서는 테스트를 실행할 수 있는 로컬 프로젝트 런타임이 제공되지 않았다.
- **다음 작업:** P5-3에서 React와 레거시의 공유 CSS를 분리하고, 저장 상태 및 API 계약을 정리한다. 이후 P5-4에서 레거시 진입 경로와 파일을 실제 제거한다.
