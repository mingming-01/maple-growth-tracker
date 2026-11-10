# Maple Growth Tracker

메이플스토리 캐릭터의 **현재 정보뿐 아니라, 시간에 따라 쌓이는 성장 과정**을 기록하고 돌아보는 개인 성장 기록·분석 서비스입니다.

레벨과 경험치, 랭킹의 변화를 날짜별로 모으고, 실제로 확인된 기록을 바탕으로 성장 흐름과 다음 레벨 목표를 살펴봅니다. 다른 캐릭터와의 비교, 장비·스탯 상세 조회, AI 성장 리포트까지 한곳에서 이어서 확인할 수 있습니다.

<p align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white)
![React](https://img.shields.io/badge/React-149ECA?style=flat-square&logo=react&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black)
![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?style=flat-square&logo=chart.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)

</p>

- **서비스:** https://maple-growth-tracker.onrender.com/
- **GitHub:** https://github.com/mingming-01/maple-growth-tracker

---

## 프로젝트가 해결하려는 것

캐릭터 조회 한 번으로 확인할 수 있는 것은 대부분 현재 시점의 정보입니다. 하지만 캐릭터가 얼마나 성장했는지 알려면 오늘의 레벨만이 아니라, 며칠 전과 비교해 경험치가 얼마나 늘었는지, 레벨업은 언제 있었는지, 랭킹은 어떻게 움직였는지 함께 봐야 합니다.

Maple Growth Tracker는 이 변화를 날짜별 기록으로 쌓아 **현재 상태와 성장의 흐름을 함께 살펴볼 수 있도록** 만든 서비스입니다.

주요 화면은 다음과 같이 구성되어 있습니다.

| 화면 | 살펴볼 수 있는 내용 |
| --- | --- |
| 개요 | 캐릭터 프로필, 현재 레벨 진행률·전투력, 랭킹, 자동 성장 인사이트 |
| 성장 분석 | 7·30·90일 성장 요약, 추이 그래프, 주요 성장 타임라인, 레벨업 예상, 목표 레벨 |
| 날짜별 기록 | 날짜별 레벨·경험치·랭킹·레벨 진행률 |
| 캐릭터 상세 | 스탯, 장비, 심볼, 6차·HEXA, 링크 스킬, 유니온 |
| AI 리포트 | 선택 기간의 성장 기록을 바탕으로 한 5개 항목의 자연어 분석 |
| 캐릭터 비교 | 두 캐릭터의 성장 지표와 동일 기간 기록 비교, AI 비교 설명 |
| 관리자 | 서비스 이용 로그와 서버 성능 계측 |

## 주요 기능

### 캐릭터 현황과 성장 인사이트

캐릭터명으로 조회하면 캐릭터 이미지, 월드, 직업, 길드, 레벨, 현재 경험치와 레벨 진행률을 확인할 수 있습니다. 종합·월드·직업별 랭킹 네 종류와 현재 전투력도 함께 표시합니다.

개요 화면의 **성장 인사이트**는 AI가 아니라 애플리케이션에서 계산하는 요약입니다. 최근 기록이 충분하면 직전 기간과 최근 기간의 일일 평균 경험치를 비교하고, 다음 레벨 예상과 저장된 랭킹 변화 등 확인 가능한 정보를 보여줍니다.

전투력은 Nexon API에서 확인한 현재 값을 표시하며, 저장된 관측값 중 최고값과 갱신 시점도 별도로 기록합니다. 랭킹은 Nexon API가 반환한 집계 기준의 스냅샷이며 실시간 순위 변화를 스트리밍하는 기능은 아닙니다.

### 성장 기록과 추이 분석

- 기본 캐릭터 조회 시 최근 7일의 날짜별 레벨·경험치·랭킹 기록을 가져옵니다.
- 성장 분석 화면에서 30일 또는 90일을 선택하면 해당 기간의 저장 기록을 조회하고, 사용자가 요청한 경우 비어 있는 날짜를 Nexon API에서 보충합니다.
- 과거 기록 보충은 10일 단위로 나누어 진행하며, 이미 저장된 기록은 재사용합니다.
- 성장 요약은 최근 확인된 경험치 증가량, 최근 7일 합계와 평균, 랭킹 변화 등을 보여줍니다.
- 30일·90일 분석은 같은 길이의 바로 이전 기간 기록이 있을 때 성장량과 평균을 비교합니다.
- 성장 타임라인에는 확인된 레벨업과 주요 성장·랭킹 기록을 표시합니다.

성장 추이 그래프는 첫 기록 이후 누적된 경험치 증가량, 날짜별 경험치 증가량, 레벨업 시점을 함께 보여줍니다. **Chart.js는 여전히 사용합니다.** React 화면에서는 성장 분석 화면에 진입할 때 동적으로 불러오고, 기존 `/legacy/` 화면에서는 `templates/index.html`의 CDN 스크립트로 불러옵니다.

### 날짜별 성장 기록과 계산 기준

날짜별 기록 화면에서는 레벨, 경험치, 경험치 증가량, 랭킹, 현재 레벨 진행률을 확인할 수 있습니다. 같은 레벨로 이어지는 연속 날짜의 진행률 변화는 `%p`로 표시합니다.

수치가 그럴듯해 보이는 것보다 실제 기록에 근거하는 것을 우선합니다.

- 기록이 없는 날짜는 경험치 증가량 0으로 취급하지 않습니다.
- 날짜가 끊긴 구간이나 레벨업으로 경험치 기준이 바뀐 구간은 임의로 보간하지 않습니다.
- 경험치 증가량과 일평균은 계산 가능한 관측 구간을 기준으로 산출합니다.
- Nexon API가 아직 당일 자료를 공개하지 않은 경우와 조회에 실패한 경우, 아직 수집하지 않은 경우를 구분합니다.
- 다음 레벨 예상은 최근 7일에 최소 네 개의 계산 가능한 경험치 변화가 있고 평균 성장량이 양수일 때만 구체적인 날짜를 표시합니다. 최근 평균 속도가 유지된다는 가정의 참고값이며 확정 일정은 아닙니다.

### 레벨업 목표

다음 레벨의 목표 날짜를 설정하고 목표 진척률을 확인할 수 있습니다. 목표일까지 필요한 하루 진척률과 최근 기록에서 관측된 하루 진척률을 비교합니다.

목표는 브라우저에 저장됩니다. 브라우저 알림을 허용하면 캐릭터를 다시 조회해 레벨업이나 목표 달성을 확인했을 때 알림을 표시할 수 있습니다. 백그라운드 푸시 알림은 제공하지 않습니다.

### 캐릭터 상세 정보

상세 화면은 탭을 선택했을 때 해당 영역의 정보를 별도로 조회합니다. 기본 캐릭터 검색에 모든 상세 API를 한꺼번에 묶지 않으며, 상세 영역의 응답은 서버에서 짧은 시간 캐시합니다.

| 탭 | 포함 정보 |
| --- | --- |
| 스탯 | 주요 스탯, 하이퍼 스탯, 어빌리티 |
| 장비 | 장비 프리셋, 헤어·성형·피부, 안드로이드, 세트 효과, 캐시 장비·외형, 펫 |
| 심볼 | 아케인·어센틱 심볼 |
| 스킬 | 6차 스킬, HEXA 코어, HEXA 스탯 |
| 링크 | 링크 스킬 프리셋 |
| 유니온 | 유니온 기본 정보·스탯, 아티팩트, 챔피언 |

Nexon API가 제공하는 프리셋을 선택해 내용을 비교할 수 있습니다. 화면에서 프리셋을 선택해도 게임 내 설정은 변경되지 않습니다. 각 상세 API의 일부가 실패해도 기본 캐릭터 정보와 성장 기록 조회는 별도로 동작합니다.

### 캐릭터 성장 비교

다른 캐릭터를 검색해 두 캐릭터의 레벨, 현재 레벨 진행률, 최근·평균 성장량, 랭킹 변화와 레벨업 예상 등을 나란히 확인합니다.

7일·30일·90일의 동일한 기간으로 성장 기록을 비교할 수 있으며, 확인된 경험치 증가량과 일평균, 랭킹 변화, 기록이 남은 날짜를 함께 표시합니다. 데이터가 부족하거나 확인되지 않은 날짜는 별도로 구분하며, 누락 구간을 임의로 추정하지 않습니다. 두 캐릭터의 성장 흐름을 설명하는 AI 비교 분석도 제공합니다.

### AI 성장 리포트

AI 리포트는 선택한 7일·30일·90일 성장 기록을 바탕으로 다음 다섯 항목을 작성합니다.

1. 성장 패턴
2. 성장 변화
3. 레벨업 분석
4. 성장 전망
5. AI 코멘트

경험치 증가량과 기간별 비교 등 수치 계산은 애플리케이션에서 수행하고, AI는 계산된 값과 기록을 자연어로 해석합니다. 분석 화면에는 기준일, 확인된 기록 수, 데이터 충실도 등 분석 근거도 표시합니다. 기록이 충분하지 않으면 근거 없는 추세나 예측을 단정하지 않도록 구성했습니다.

새 AI 리포트는 사용자가 분석을 시작할 때 생성합니다. 이전 결과가 브라우저 캐시에 남아 있으면 보관 기간 안에서 다시 불러올 수 있으며, 새 결과를 원할 때는 다시 분석할 수 있습니다. AI 제공자는 Gemini를 우선 사용하고, 설정 및 오류 조건에 따라 OpenRouter를 대체 경로로 사용합니다.

### 관심 캐릭터와 결과 저장

- 관심 캐릭터를 최대 30명까지 브라우저에 저장하고 다시 조회할 수 있습니다.
- 검색 결과와 화면 상태는 현재 탭의 `sessionStorage`에 저장되어 같은 탭에서 새로고침해도 복원됩니다.
- 관심 캐릭터, 레벨업 목표와 AI 리포트 캐시는 브라우저 `localStorage`를 사용합니다. 브라우저 또는 기기 사이에 자동 동기화되지는 않습니다.
- 검색 결과 화면을 PNG 이미지 또는 여러 페이지의 A4 PDF로 저장할 수 있습니다.

### 관리자 기능

관리자 화면에서 로그인 후 캐릭터 조회, AI 분석, 비교 등 서비스 이용 로그를 검색하고 확인할 수 있습니다. 별도의 성능 API는 현재 서버 프로세스에서 수집한 요청·캐시·외부 API·DB 관련 계측값을 제공합니다. 성능 계측은 프로세스 단위이므로 여러 워커의 값을 하나로 합산한 지표는 아닙니다.

---

## 기술 구성

| 영역 | 사용 기술 |
| --- | --- |
| Backend | Python, Flask, Requests, Gunicorn |
| Frontend | React 19, React DOM, Vite 6, JavaScript |
| 그래프 | Chart.js 4 — 성장 분석 화면에서 지연 로딩 |
| 이미지·PDF 저장 | html2canvas, jsPDF |
| 게임 데이터 | NEXON Open API |
| AI | Google Gemini API, OpenRouter |
| 서버 데이터 저장 | PostgreSQL, SQLite |
| 테스트 | Python unittest, Node.js test runner, Playwright |
| 배포 | Render |

### 주요 디렉터리

```text
maple-growth-tracker/
├── app.py
├── package.json
├── requirements.txt
├── frontend/
│   ├── package.json
│   └── src/
│       ├── components/       # 캐릭터 상세·관리자 등 공통 UI
│       ├── features/         # 개요·성장·분석 화면
│       ├── lib/              # 성장 계산·기록 수집·브라우저 저장
│       ├── services/         # Flask API 클라이언트
│       └── styles/
├── tracker/
│   ├── application.py        # Flask 앱 팩토리와 Blueprint 등록
│   ├── config.py
│   ├── runtime.py
│   ├── controller/           # HTTP 요청·응답
│   ├── domain/               # 성장 지표·AI 분석 근거 계산
│   ├── integrations/         # Nexon·AI 외부 API 연동
│   ├── repositories/         # DB·스냅샷 저장소
│   └── services/             # 수집·캐시·분석·요청 제한
├── static/                   # 레거시 화면 자산 및 React 빌드 산출물
├── templates/                # 레거시·관리자 템플릿
├── migrations/
├── tests/                    # Python 테스트
├── tests-js/                 # JavaScript 단위 테스트
├── e2e/                      # 브라우저 테스트
└── docs/
```

## API 개요

| 경로 | 설명 |
| --- | --- |
| `GET /api/character?name=` | 캐릭터 기본 정보, 네 종류 랭킹, 현재 전투력 |
| `GET /api/history?name=&ocid=` | 최근 7일 성장 기록 |
| `GET /api/history/archive?ocid=&days=` (days는 30 또는 90) | 저장된 기간 기록 조회 및 요청된 과거 기록 보충 |
| `GET /api/character-details?ocid=&section=` | 선택 영역의 상세 정보 조회 |
| `POST /api/ai-analysis?name=` | 선택 기간의 성장 지표·기록을 바탕으로 AI 리포트 생성 |
| `POST /api/ai-comparison` | 두 캐릭터의 성장 지표 비교 설명 생성 |
| `GET /admin/api/logs` | 관리자 이용 로그 조회 |
| `GET /admin/api/performance` | 현재 프로세스의 성능 계측 조회 |

`/api/character-details`의 `section`은 `stats`, `equipment`, `symbols`, `skills`, `link`, `union`을 사용합니다. AI 분석의 `GET /api/ai-analysis`는 과거 호출과의 호환을 위해 남아 있으며, 현재 프런트엔드는 `POST`를 사용합니다.

## 데이터와 운영 기준

### 서버 저장소

`GROWTH_DATABASE_URL`에 유효한 PostgreSQL 연결 문자열을 설정하면 성장 기록, API 스냅샷, 관리자 로그 등 서버 측 저장소가 PostgreSQL을 사용합니다. 로컬에서 이 값이 없으면 SQLite를 개발용 저장소로 사용합니다. 저장소별 연결 실패 처리와 폴백 방식은 다를 수 있으므로 관리자 화면의 저장 상태와 서버 로그를 함께 확인해야 합니다. Render에서 재배포 이후에도 기록을 유지하려면 영속 PostgreSQL 연결을 설정하는 편이 안전합니다.

서버 메모리 캐시와 성능 계측값은 프로세스가 재시작되면 초기화됩니다. 관리자 성능 화면은 현재 요청을 처리한 프로세스의 계측 결과를 보여줍니다.

### 외부 API와 데이터 한계

NEXON Open API가 반환하는 정보와 공개 시점에 따라 기록을 확보할 수 있는 범위가 달라집니다. 특히 당일 랭킹이나 과거 날짜 데이터가 아직 공개되지 않았거나 API에서 조회되지 않을 수 있습니다. 이런 경우 실제 기록과 미수집·조회 실패 상태를 구분해 표시하며, 없는 데이터를 만들어 채우지 않습니다.

AI 분석은 참고용 자연어 해석입니다. 성장량·평균·랭킹 변화 등 계산이 가능한 수치는 코드에서 산출하고, AI 응답은 검증과 후처리를 거쳐 표시합니다.

운영 환경의 관리자 인증에는 `ADMIN_PASSWORD_HASH`를 사용합니다. 평문 `ADMIN_PASSWORD`는 로컬 개발 환경에서만 허용됩니다. API 키와 비밀번호 등 민감한 값은 코드에 작성하지 말고 환경변수로 관리합니다.

---

## 로컬 개발 환경

### 1. 저장소 복제 및 가상환경 준비

```bash
git clone https://github.com/mingming-01/maple-growth-tracker.git
cd maple-growth-tracker

python -m venv .venv
```

Windows Git Bash:

```bash
source .venv/Scripts/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 2. 의존성 설치

Python, 루트 개발 도구, React 프런트엔드 의존성을 설치합니다.

```bash
pip install -r requirements.txt
npm ci
npm --prefix frontend ci
```

### 3. 환경변수 설정

프로젝트 루트에 `.env` 파일을 만들고 필요한 값을 설정합니다.

```env
NEXON_API_KEY=YOUR_NEXON_API_KEY

# AI 기능을 사용할 때 설정
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY
OPENROUTER_MODEL=openrouter/free

# 관리자 기능
ADMIN_USERNAME=YOUR_ADMIN_ID
ADMIN_PASSWORD_HASH=YOUR_PASSWORD_HASH

# 영속 PostgreSQL 저장소를 사용할 때 설정
GROWTH_DATABASE_URL=postgresql://...

# 운영 환경에서 고정된 세션 키 사용
FLASK_SECRET_KEY=YOUR_LONG_RANDOM_SECRET
```

| 변수 | 용도 |
| --- | --- |
| `NEXON_API_KEY` | NEXON Open API 인증 키 |
| `GEMINI_API_KEY` | 기본 AI 제공자 인증 키 |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | 대체 AI 제공자 및 모델 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH` | 관리자 계정 |
| `GROWTH_DATABASE_URL` | PostgreSQL 연결 문자열. 미설정 시 로컬 SQLite 사용 |
| `FLASK_SECRET_KEY` | Flask 세션 서명 키 |

AI와 관리자 기능은 관련 환경변수가 설정되지 않으면 사용할 수 없습니다. 운영 환경에서는 관리자 비밀번호 해시와 충분히 긴 고정 세션 키를 설정해야 합니다.

### 4. 개발 서버 실행

저장소 루트에서 다음 명령 하나로 Flask 백엔드와 Vite 개발 서버를 함께 실행합니다.

```bash
npm run dev
```

- React 개발 화면: http://127.0.0.1:5173/
- Flask 백엔드: http://127.0.0.1:5000/

프런트엔드 개발 서버는 `/api`, `/static`, `/admin` 요청을 Flask로 프록시합니다. 필요하면 `FLASK_API_PROXY_TARGET`으로 백엔드 주소를 변경할 수 있습니다.

별도 실행이 필요할 때는 다음 명령을 각각 사용할 수 있습니다.

```bash
npm run dev:backend
npm run dev:frontend
```

## 테스트와 빌드

```bash
# Python 단위·통합 테스트
python -m unittest discover -s tests -v

# JavaScript 성장 지표 테스트
npm run test:growth

# React 프로덕션 빌드
npm --prefix frontend run build

# Playwright 브라우저 테스트
npm run test:e2e
```

현재 `Tests` GitHub Actions 워크플로는 Python 테스트, React 빌드, 레거시 JavaScript 구문 검사, JavaScript 성장 지표 테스트를 실행합니다. Playwright 명령은 별도 실행 스크립트이며 해당 워크플로의 기본 검사 항목과는 구분됩니다.

## 배포

서비스는 Render에서 운영합니다.

- 서비스 주소: https://maple-growth-tracker.onrender.com/
- React 프로덕션 빌드 산출물: `static/react-preview/`
- React 빌드가 존재하면 `/`에서 React 화면을 제공하고, 빌드 산출물이 없으면 `/`는 기존 레거시 화면으로 폴백합니다.
- 기존 화면은 `/legacy/`, React 빌드 미리보기는 `/preview/`에서 확인할 수 있습니다.

Render 빌드 과정에서는 Python 의존성과 프런트엔드 의존성을 설치한 뒤 React 빌드를 생성해야 합니다.

```bash
pip install -r requirements.txt && npm --prefix frontend ci --no-audit --no-fund && npm --prefix frontend run build
```

배포 환경변수에는 Nexon API 키, 필요한 AI 제공자 키, 관리자 인증 값, 고정 Flask 세션 키, PostgreSQL 연결 문자열 등을 등록합니다.

---

## 관련 문서

- [문서 안내](docs/README.md)
- [새로고침과 데이터 최신성](docs/REFRESH_BEHAVIOR.md)
- [성장 기록 저장](docs/GROWTH_HISTORY_STORAGE.md)
- [캐릭터 상세 정보](docs/PHASE3_CHARACTER_DETAILS.md)
- [Phase 1 운영 안정성](docs/PHASE1_HARDENING.md)
- [성능 계측](docs/PERFORMANCE_METRICS.md)
