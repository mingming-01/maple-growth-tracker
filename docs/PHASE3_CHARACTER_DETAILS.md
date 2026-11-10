# 캐릭터 상세 정보

## 목적

성장 기록과 별도로 캐릭터의 현재 상세 구성을 확인한다. 기본 캐릭터 검색 응답은 유지하고, 상세 데이터는 사용자가 각 탭을 열 때 해당 영역을 지연 조회한다.

## 화면 구성

| 상세 영역 | 표시 데이터 |
|---|---|
| 스탯 | 주요 스탯, 현재 적용 전투력, 하이퍼 스탯 프리셋, 어빌리티 프리셋 |
| 장비 | 장비 프리셋, 헤어·성형·피부, 안드로이드, 세트 효과, 캐시 장비·외형 프리셋, 펫 |
| 심볼 | 아케인·어센틱 심볼 |
| 스킬 | 6차 스킬, HEXA 코어, HEXA 스탯 |
| 링크 | 링크 스킬 프리셋 |
| 유니온 | 유니온 기본 정보, 유니온 스탯 프리셋, 아티팩트, 챔피언 |

프리셋은 각 데이터 영역에서 독립적으로 선택한다. 장비 1번과 하이퍼 스탯 1번 등이 같은 조합이라는 가정은 하지 않는다. Nexon 응답에 존재하는 프리셋만 선택지로 제공한다.

## Nexon API 연동

| 상세 영역 | Nexon Open API 경로 |
|---|---|
| 주요 스탯 | `character/stat` |
| 하이퍼 스탯 | `character/hyper-stat` |
| 어빌리티 | `character/ability` |
| 헤어·성형·피부 | `character/beauty-equipment` |
| 장비 | `character/item-equipment` |
| 안드로이드 | `character/android-equipment` |
| 세트 효과 | `character/set-effect` |
| 캐시 장비·외형 | `character/cashitem-equipment` |
| 펫 | `character/pet-equipment` |
| 심볼 | `character/symbol-equipment` |
| 링크 스킬 | `character/link-skill` |
| 유니온 기본 | `user/union` |
| 유니온 스탯 | `user/union-raider` |
| 유니온 아티팩트 | `user/union-artifact` |
| 유니온 챔피언 | `user/union-champion` |
| 6차 스킬 | `character/skill` (6차 등급 파라미터) |
| HEXA 코어 | `character/hexamatrix` |
| HEXA 스탯 | `character/hexamatrix-stat` |

모든 상세 조회는 OCID를 기준으로 수행한다. 라우트는 `GET /api/character-details?ocid=...&section=...`이며 `section`에는 `stats`, `equipment`, `symbols`, `skills`, `link`, `union`을 사용한다.

## 지연 조회와 실패 처리

- 기본 캐릭터 검색은 상세 정보 API를 한꺼번에 호출하지 않는다.
- 사용자가 상세 탭을 선택하면 해당 영역에 속한 Nexon API를 요청한다.
- 동일 OCID와 상세 영역의 응답은 서버 메모리에 5분 캐시한다.
- 영역 안의 일부 API만 실패하면 성공한 데이터는 표시하고 실패한 소스만 조회 불가 상태로 구분한다.
- 상세 API가 실패해도 캐릭터 기본 정보, 성장 그래프, 기간별 통계에는 영향을 주지 않는다.
- 정상 응답의 빈 데이터와 HTTP 오류·연결 오류를 구분한다.

## 프리셋 및 전투력 표시 원칙

- Nexon API 응답의 활성 프리셋 번호를 기본 선택으로 사용한다.
- 실제 응답에 존재하는 프리셋만 선택지로 표시한다. API가 제공하지 않는 프리셋을 임의로 만들지 않는다.
- 주요 스탯 API의 `final_stat`에서 `전투력` 항목을 찾으면 현재 적용 상태의 전투력을 별도로 표시한다.
- 프리셋별 전투력 또는 환산 점수가 API 응답에 별도로 포함되지 않는 경우, 비활성 프리셋의 전투력·환산 점수를 추정하거나 최고 프리셋이라고 단정하지 않는다.
- 프리셋 구성 데이터만으로 실제 전투력이나 환산 주스탯을 재현하려면 게임 계산식, 버프 조건, 보스 설정 등 추가 조건이 필요하다. API가 반환한 현재 전투력과 프리셋 구성 비교는 구분한다.

## 테스트 범위

- 프리셋 번호, 프리셋 데이터 및 현재 적용 상태 추출
- 장비·캐시 외형·링크·유니온 스탯 프리셋 정규화
- 심볼·스킬·유니온 세부 소스 처리
- 현재 전투력 추출 및 프로필 조회와 상세 스탯 캐시의 연계
- 일부 Nexon API 실패 시 부분 성공 상태 반환
- 상세 라우트의 OCID·영역 검증
- Playwright에서 모바일 상세 UI와 기본 프로필 갱신 후 열린 상세 전투력의 동기화 확인
