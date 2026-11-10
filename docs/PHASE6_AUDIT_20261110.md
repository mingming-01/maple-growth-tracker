# Phase 6 — 중복·죽은 코드·레거시 1차 감사

- 기준 브랜치: `main`
- 기준 커밋: `4ae155a3cc36117cfd06bf3c8258080e08ade395`
- 작업 브랜치: `refactor/phase6-legacy-cleanup-20261110`
- 감사 범위: 저장소 트리 전체 확인, 백엔드 런타임·컨트롤러·서비스·저장소·연동 모듈과 관련 테스트, 레거시/React 진입 경로의 참조 확인
- 상태: **1차 정적 감사. 코드 수정·삭제 및 테스트 실행 없음.**

## 1. 요약

이번 1차 조사에서 P5 직후 눈에 띄는 호환 코드와 레거시 자산을 실제 사용처까지 추적했다. 현재 확인된 범위에서는 즉시 삭제해도 안전하다고 입증된 큰 코드 묶음은 없다.

특히 다음 항목은 겉보기에는 오래되었거나 중복처럼 보이지만 현재 실행 경로 또는 테스트 계약이 있어 삭제하면 안 된다.

- `app.py`의 `sys.modules` 호환 처리와 `runtime.py`의 일부 공개 이름
- `runtime.py`의 캐시·로그·스냅샷 위임 함수
- `history_controller.py`의 `ThreadPoolExecutor`
- `static/` 및 `templates/index.html`의 레거시 화면 자산
- `static/jobs.json`

따라서 Phase 6은 우선 **중복 규칙의 통합 가능성을 검토하고, 사용처가 확인된 호환 코드는 유지**하는 방향으로 진행한다.

## 2. 확인된 유지 대상

| 항목 | 현재 참조 근거 | 판정 |
|---|---|---|
| `app.py`의 `sys.modules[__name__] = runtime` | `tests/test_admin_logs.py`, `test_ai_analysis_cache.py`, `test_api_resilience.py`, `test_growth_calculations.py`, `test_growth_history_store.py` 등이 `import app as tracker` 후 런타임 속성·함수를 사용 | 삭제 금지. 테스트와 구형 호출 인터페이스를 먼저 명시적 import로 이전해야 함 |
| `runtime.initialize_log_db` | 앱 런타임 초기화에서 호출되고 관리자 로그 테스트도 직접 호출 | 유지 |
| `runtime.log_action` | `record_user_action`의 요청 후처리에서 호출되고 테스트에서도 직접 호출 | 유지 |
| `runtime.connect_log_db` | 현재 테스트에서 직접 호출 | 테스트 계약 또는 호환 API를 정리하기 전까지 유지 |
| 캐시 위임 함수 | 캐릭터·히스토리·상세 컨트롤러 및 AI 분석 서비스가 사용 | 유지 |
| 스냅샷 위임 함수 | 캐릭터·히스토리 컨트롤러가 사용하고 최고 전투력 기록도 사용 | 유지 |
| `history_controller.ThreadPoolExecutor` | 장기 기록 보충 수집 경로에서 `max_workers=4`로 사용 | 제거 금지. P5에서 이동한 것은 최근 7일 수집 경로이며 장기 보충 경로는 아직 컨트롤러에 남아 있음 |
| `static/app.js`, `static/js/*`, `templates/index.html` | `/legacy/` 라우트 및 React 빌드가 없을 때 루트 경로의 폴백에서 레거시 템플릿이 실행 | 운영 React 전환과 레거시 폐기 승인이 있기 전 삭제 금지 |
| `static/jobs.json` | `nexon_service._jobs_path()`가 파일 경로를 조합해 직업 분류 폴백에 사용 | 유지 |
| `get_ranking_page` | `tests/test_nexon_api_ranking.py`가 직접 테스트 | 현재 테스트 참조가 있으므로 죽은 코드로 판정하지 않음 |

### 런타임 호환 함수 참조 요약

- `get_cache`: 캐릭터·히스토리·상세 컨트롤러에서 사용
- `set_cache`: 캐릭터·히스토리·상세 컨트롤러에서 사용
- `delete_cache`: 캐릭터 컨트롤러에서 상세 통계 캐시 무효화에 사용
- `get_cache_timestamp`: 캐릭터·히스토리 컨트롤러에서 사용
- `get_ai_response_cache` / `set_ai_response_cache`: AI 분석 서비스에서 사용
- `save_api_snapshot` / `load_api_snapshot`: 캐릭터·히스토리 흐름 및 최고 전투력 기록에서 사용
- `log_action`: Flask `after_request` 후처리에서 사용

이 함수들은 새 Service/Repository로 위임하는 얇은 경계이지만 실제 호출자가 남아 있으므로 현재 단계에서 삭제할 수 없다.

## 3. 중복 코드 후보

| ID | 위치 | 확인한 사실 | 위험 및 권장 조치 |
|---|---|---|---|
| P6-DUP-01 | `static/js/growth.js`, `frontend/src/lib/growth.js` | Git blob SHA와 파일 크기(14,056 bytes)가 동일함. 레거시 `static/app.js`는 전자를 import하고 React 코드도 프론트엔드 모듈을 사용 | 실제 중복 구현은 맞지만 양쪽이 모두 활성 경로다. 단순 삭제 금지. 공통 소스 위치 또는 빌드 시 복사 전략을 설계한 뒤 별도 변경 |
| P6-DUP-02 | `tracker/services/ai_analysis_service.py` | 성장 분석과 캐릭터 비교에 Gemini → OpenRouter 폴백 흐름이 각각 존재 | 성장 분석은 출력 검증·결정론적 전망 보정이 있고 비교는 다른 응답 계약을 사용한다. 공급자 호출 부분만 공통화할 수 있는지 검토하고 응답 후처리 차이는 보존 |
| P6-DUP-03 | `tracker/integrations/nexon_api.py`, `tracker/integrations/ai_provider.py`, `tracker/services/request_limits.py` | 설정을 읽는 `_setting` 함수가 반복됨. 앞의 두 함수는 앱 컨텍스트 및 `Config` 폴백 구조가 같고 request_limits 버전은 앱 컨텍스트가 없을 때 기본값을 사용 | 앞의 두 함수는 공통화 후보. request_limits는 동작이 다르므로 무조건 통합하지 말고 스레드 작업자 등 앱 컨텍스트 외부 호출을 확인 |
| P6-DUP-04 | `tracker/controller/history_controller.py` 장기 기록 수집 | 누락/재수집 필요 조건이 `missing_dates`와 `remainingDays` 계산에 반복됨 | 동일 판정식의 불일치 위험이 있음. 순수 함수로 추출해 두 경로가 같은 규칙을 사용하도록 테스트 우선 작성 |
| P6-DUP-05 | 시간대 상수 | runtime, admin log service, admin log repository 등에서 KST 시간대 객체를 별도로 생성 | 작은 중복. 통합 이득은 제한적이므로 우선순위 낮음. 날짜 직렬화·DB timezone 동작을 확인하지 않고 변경하지 않음 |

## 4. 죽은 코드 후보 — 추가 확인 필요

| 항목 | 현재 확인 결과 | 다음 확인 |
|---|---|---|
| `character_detail_service._fetch_champion_image` | 현재 확인한 애플리케이션 코드와 테스트에서 직접 호출 참조를 찾지 못함. 함수 설명은 기존 호출부 호환 목적이라고 명시 | 저장소 전체 참조 및 외부 호출 계약을 다시 확인한 뒤 제거 여부 결정 |
| `runtime.connect_log_db` | 운영 요청 흐름에서는 직접 호출을 찾지 못했지만 테스트에서 직접 사용 | 테스트를 Repository/Service 계약으로 이전할지 결정하기 전 삭제 금지 |
| `app.py`의 런타임 모듈 별칭 | 현재 여러 테스트가 의존 | 테스트와 WSGI 진입점 호환성 이전 계획이 먼저 필요 |

현재 조사만으로 미사용이 확인된 항목은 없다. 위 항목은 **삭제 승인 목록이 아니라 추가 확인 목록**이다.

## 5. 문서 신뢰도 점검

- `docs/PROJECT_FULL_AUDIT_REPORT.md`는 기준 커밋을 `259acf6`로 명시한 부분 감사 문서이며, 테스트·빌드·전체 grep을 실행하지 않았다고 스스로 밝힌다. P5 병합 후의 현재 코드를 설명하는 최신 감사 결과로 취급하면 안 된다.
- `docs/P5_LEGACY_CLEANUP_AUDIT.md`도 과거 브랜치 기준 문서다. 현재 실행 경로를 다시 확인하는 참고 자료로만 사용한다.
- 문서의 후보·개수·위험도는 현재 코드에서 재확인하기 전까지 확정 사실로 사용하지 않는다.

## 6. 다음 작업 제안

1. `_setting` 중복과 히스토리 재수집 판정식처럼 범위가 작고 테스트 가능한 중복부터 검토한다.
2. AI 공급자 폴백 공통화는 기존 오류 분류·검증·캐시 동작을 테스트로 고정한 뒤 별도 작업으로 분리한다.
3. 레거시 화면과 `app.py` 호환 계층은 현재 사용 경로가 있으므로 즉시 삭제하지 않는다.
4. 후보별 기존 테스트를 확인하고, 필요한 회귀 테스트를 먼저 추가한 뒤 한 묶음씩 변경한다.

## 7. 감사 한계

이번 결과는 저장소 트리와 주요 백엔드·테스트·프론트엔드 진입 경로를 정적으로 추적한 1차 결과다. 전체 프로젝트를 로컬에서 실행해 동적 import, 외부 운영 스크립트, 모든 브라우저 경로까지 증명한 것은 아니다. 이번 단계에서는 코드 변경이나 삭제를 하지 않았고, 테스트도 실행하지 않았다.
