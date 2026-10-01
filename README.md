# Maple Growth Tracker

메이플스토리 캐릭터의 현재 스펙이 아니라 **성장 과정**을 기록하고, 계산된 성장 데이터를 이해하기 쉽게 보여주는 웹 서비스입니다.

<p align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black)
![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?style=flat-square&logo=chart.js&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini%20API-4285F4?style=flat-square&logo=google&logoColor=white)
![OpenRouter](https://img.shields.io/badge/OpenRouter-6467F2?style=flat-square)

</p>

- 서비스: https://maple-growth-tracker.onrender.com/
- GitHub: https://github.com/mingming-01/maple-growth-tracker

---

## 프로젝트 소개

캐릭터 검색 사이트는 대부분 지금의 레벨, 직업, 순위를 보여주는 데 집중합니다.
이 프로젝트는 방향을 조금 바꿔서 **"이 캐릭터가 최근 어떻게 성장했는가"** 를 보여주는 것을 목표로 만들었습니다.

캐릭터명을 입력하면 NEXON Open API로 캐릭터 정보와 최근 7일의 경험치·랭킹 기록을 가져오고, 서버와 브라우저에서 성장량과 레벨업 여부, 성장 지표를 계산합니다. 계산된 결과는 카드, 표, 그래프로 보여주고, 같은 지표를 AI에게 전달해 성장 흐름을 문장으로 해석한 리포트를 만듭니다.

메인 화면은 서비스 소개(성장 기록 / 성장 분석 / AI 성장 리포트)와 캐릭터 검색 영역으로 구성했고, 검색 결과는 같은 화면 아래에 이어서 표시됩니다. 상단 헤더의 로고를 누르면 저장된 결과를 지우고 처음 화면으로 돌아가며, 헤더에서 관리자 페이지로 이동할 수 있습니다.

---

## 핵심 데이터 흐름

```text
NEXON Open API
      ↓
캐릭터 / 성장 데이터 수집
      ↓
Flask / Python
      ↓
데이터 가공 및 계산
      ↓
JavaScript / Chart.js
      ↓
성장 데이터 시각화
      ↓
Gemini / OpenRouter
      ↓
AI 성장 데이터 해석
```

실제 요청 흐름은 아래와 같습니다.

```text
[캐릭터 조회]
브라우저 ─ /api/character ─→ Flask ─→ NEXON API (기본 정보 + 랭킹 4종 병렬 조회)
브라우저 ─ /api/history   ─→ Flask ─→ NEXON API (최근 7일 랭킹 기록 병렬 조회)
                              └ 경험치 증가량 / 레벨업 여부 / 랭킹 변화 계산
브라우저: 성장 요약 · 예측 · 그래프 렌더링, 성장 지표(metrics) 계산

[AI 성장 리포트]
브라우저 ─ metrics ─→ /api/ai-analysis ─→ Gemini (제한·일시 오류 시 OpenRouter)
브라우저 ←─ 리포트 문장 ─ 후처리(sanitize) ─┘
```

---

## 주요 기능

### 캐릭터 정보와 랭킹
- 캐릭터명, 월드(월드 로고 표시), 직업, 길드, 현재 레벨, 경험치 진행도
- 종합 랭킹, 월드 랭킹, 직업 랭킹(월드), 직업 랭킹(전체)

### 성장 기록과 분석
- 최근 7일 날짜별 레벨 / 경험치 / 랭킹 기록
- 어제보다 늘어난 경험치(일일 성장량), 최근 7일 성장량, 일 평균 성장량
- 전일 대비 랭킹 변화
- 레벨업 판단과 표시

### 성장 그래프
- Chart.js 이중 축 그래프: 누적 경험치(선) + 일일 상승량(점선)
- 레벨업한 날은 별 모양으로 표시하고, 툴팁에 이전 레벨 → 현재 레벨 표시
- 레벨업으로 경험치가 초기화되어도 그래프가 급락하지 않도록 별도 처리 (아래 "주요 문제 해결" 참고)

### 성장 예측
- 현재 경험치와 진행률로 해당 레벨의 전체 필요 경험치를 역산하고, 최근 평균 성장량이 유지된다고 가정해 다음 레벨까지 남은 경험치, 예상 소요일, 예상 날짜를 계산합니다.
- 어디까지나 가정에 기반한 예상치이며, 화면에도 그 점을 안내합니다. 최근 평균 성장량을 구할 수 없으면 예측 카드를 비우고, 진행률이 0%이거나 100% 이상이라 역산할 수 없으면 남은 경험치·소요일·예상 날짜를 `-`로 표시합니다.

### AI 성장 리포트
- 계산된 지표를 바탕으로 성장 패턴 / 성장 변화 / 레벨업 분석 / 성장 전망 / AI 코멘트 5개 항목을 생성합니다. (자세한 내용은 아래 섹션)

### 캐릭터 성장 비교
- 현재 조회한 캐릭터와 비교할 캐릭터를 같은 기준의 지표(레벨, 경험치 진행도, 최근·평균·7일 성장량, 랭킹 변화, 예상 레벨업)로 나란히 비교합니다.
- 두 캐릭터의 계산된 지표를 AI에게 전달해 성장 흐름의 차이를 설명하는 비교 분석을 생성합니다.
- 같은 캐릭터끼리의 비교는 브라우저와 서버 양쪽에서 막습니다.

### 이미지 / PDF 저장
- 결과 화면을 html2canvas로 캡처해 PNG로 저장하거나, jsPDF로 A4 PDF(여러 페이지)로 저장합니다.

### 화면 상태 유지
- 검색 결과, AI 리포트, 비교 결과를 `sessionStorage`에 저장합니다. 새로고침(F5, Ctrl+Shift+R) 후에도 같은 탭에서는 결과가 유지되고, 탭을 닫거나 헤더의 로고를 누르면 초기 화면으로 돌아갑니다.

### 관리자 기능
- 관리자 로그인 후 최근 사용 로그(캐릭터 조회, AI 성장 분석, 캐릭터 비교, 서비스 오류)를 최대 500건까지 확인할 수 있습니다.

---

## AI 성장 리포트

AI 리포트는 아래 구조로 동작합니다.

```text
성장 데이터 계산 (Python / JavaScript)
      ↓
Gemini API
      ↓
정상 응답 ─────────────────────→ AI 성장 리포트

Gemini 요청 제한 / 일시적 오류
      ↓
OpenRouter fallback ───────────→ AI 성장 리포트
```

fallback은 코드에서 다음 조건으로 동작합니다.

- Gemini 호출이 실패했을 때 오류 내용에 `429`, `RESOURCE_EXHAUSTED`, `QUOTA`, `503`, `504`, `TIMEOUT` 중 하나가 포함되면 OpenRouter로 다시 요청합니다.
- 위에 해당하지 않는 오류는 fallback 없이 안내 메시지만 반환합니다.
- `GEMINI_API_KEY`가 없고 `OPENROUTER_API_KEY`만 설정되어 있으면 OpenRouter로 바로 요청합니다.
- OpenRouter까지 실패하면 "AI 분석을 불러오지 못했습니다."라는 안내만 표시하고, 내부 오류 내용은 화면에 노출하지 않습니다.
- 사용할 OpenRouter 모델은 `OPENROUTER_MODEL` 환경변수로 바꿀 수 있고, 기본값은 `openrouter/free`입니다.
- 성장 리포트와 캐릭터 비교 분석에 같은 방식이 적용됩니다.

AI 응답은 그대로 쓰지 않고 서버에서 후처리합니다(`sanitize_ai_text`).

- 마크다운 기호(제목, 굵게, 목록, 코드 블록 등) 제거
- 프롬프트에 넘긴 내부 키 이름(`rankingChange`, `levelUps` 등)이나 `null` 같은 값이 응답에 섞여 나오면 자연스러운 한국어로 치환
- 긴 원본 경험치 숫자가 그대로 노출되면 문구로 대체
- 성장 전망에 적힌 날짜를 화면의 예측 카드와 같은 날짜로 맞춤

---

## 데이터와 AI의 역할 분리

이 프로젝트에서 가장 신경 쓴 부분은 **계산은 애플리케이션이, 해석은 AI가** 맡도록 나눈 것입니다.

| 역할 | 담당 |
| --- | --- |
| 게임 데이터 수집 | NEXON Open API |
| 랭킹·기록 조회, 경험치 증가량 계산, 레벨업 판단, 전일 대비 랭킹 변화 | Flask / Python |
| 일일·평균·7일 성장량, 성장 예측, AI에 전달할 성장 지표(metrics) 계산 | JavaScript |
| 성장 데이터 시각화 | Chart.js |
| 성장 패턴 해석, 자연어 리포트 | Gemini API / OpenRouter |

LLM은 숫자 계산이 틀리거나 없는 내용을 그럴듯하게 채워 넣을 수 있습니다. 그래서 경험치 증가량, 레벨업 여부, 평균, 예측 날짜처럼 코드로 정확히 구할 수 있는 값은 먼저 계산하고, AI에게는 **계산 결과를 해석하는 일만** 시킵니다.

프롬프트에는 다음 규칙을 넣었습니다.

- 새 숫자를 계산하거나 추정하지 않는다.
- 기록이 부족하면 판단하기 어렵다고 말한다.
- 레벨업은 기록에서 확인될 때만 언급한다.
- 플레이 방식이나 플레이 시간을 추측하지 않는다.
- 이미 화면에 표시되는 숫자는 되풀이하지 않는다.

---

## 기술 스택

| 구분 | 기술 |
| --- | --- |
| Backend | Python, Flask, requests, python-dotenv |
| Frontend | HTML, CSS, JavaScript |
| 시각화 | Chart.js |
| 이미지 / PDF 저장 | html2canvas, jsPDF |
| AI | Google Gemini API, OpenRouter |
| 게임 데이터 | NEXON Open API |
| 관리자 로그 저장 | SQLite (`sqlite3`) |
| 배포 | Render |
| 개발 환경 | Kali Linux, VS Code, Git, GitHub |

Chart.js, html2canvas, jsPDF는 CDN으로 불러옵니다.

---

## 프로젝트 구조

```text
maple-growth-tracker/
│
├── app.py                  # Flask 서버, NEXON API 호출, 성장 계산, AI 호출, 관리자 기능
├── requirements.txt
├── .gitignore
├── README.md
│
├── instance/               # 실행 시 자동 생성
│   └── admin_logs.sqlite3  # 관리자 사용 로그 (SQLite)
│
├── templates/
│   ├── index.html          # 메인 화면 / 결과 화면
│   ├── admin_login.html    # 관리자 로그인
│   └── admin_logs.html     # 관리자 로그 조회
│
└── static/
    ├── app.js              # 조회, 성장 계산, 그래프, AI 호출, 상태 저장, 이미지/PDF 저장
    ├── style.css
    ├── jobs.json           # 직업 → NEXON 랭킹 조회용 직업 값 매핑
    └── images/
        ├── logo.svg        # 사이트 로고
        └── worlds/         # 월드 로고 이미지
```

### API

| 경로 | 설명 |
| --- | --- |
| `GET /` | 메인 화면 |
| `GET /api/character?name=` | 캐릭터 정보와 랭킹 4종 |
| `GET /api/history?name=` | 최근 7일 기록과 경험치 증가량 / 레벨업 / 랭킹 변화 |
| `POST /api/ai-analysis?name=` | 계산된 지표(metrics)를 받아 AI 성장 리포트 생성 (GET은 지표 없이 호출하던 방식과의 호환용) |
| `POST /api/ai-comparison` | 두 캐릭터의 지표를 받아 AI 비교 분석 생성 |
| `/admin/login`, `/admin/logs`, `POST /admin/logout` | 관리자 로그인 / 로그 조회 / 로그아웃 |

---

## 주요 문제 해결

### 1. 레벨업 시 경험치 그래프가 급락하는 문제

레벨이 오르면 경험치 진행도가 초기화되기 때문에, 날짜별 경험치를 그대로 빼면 레벨업한 날의 증가량이 큰 음수가 됩니다. 그래프도 갑자기 떨어지는 것처럼 보였습니다.

- 서버: 전날보다 레벨이 올랐으면 그날의 `experienceChange`를 계산하지 않고(`None`) `levelUp: true`로 표시합니다.
- 브라우저: 누적 경험치 그래프는 첫 기록을 기준으로 **양수인 증가분만 더해서** 만들고, 레벨업한 날의 차이는 건너뜁니다. 대신 별 마커와 툴팁(이전 레벨 → 현재 레벨)으로 레벨업을 따로 보여줍니다.
- 평균·7일 성장량은 유효한 증가분(양수)만으로 계산합니다. 즉, 레벨업한 날의 성장량은 집계에서 제외됩니다.

### 2. 여러 랭킹 API를 병렬로 조회

캐릭터 한 명을 보여주려면 NEXON 랭킹 API를 여러 번 불러야 합니다. 종합 / 월드 / 직업+월드 / 직업 랭킹 4종은 서로 독립적인 요청이라서 `ThreadPoolExecutor`로 동시에 조회합니다. 최근 7일 기록도 날짜별 요청 7개를 같은 방식으로 병렬 처리합니다. 순차 호출로 하면 응답 시간이 요청 수만큼 늘어나기 때문입니다.

### 3. API 호출 캐시

같은 캐릭터에 대한 요청이 반복되는 구조였습니다. 조회 후 AI 분석을 요청하면 서버가 캐릭터 정보와 성장 기록을 다시 조회하기 때문입니다. 그래서 서버 메모리에 TTL 캐시를 두었습니다.

- 캐릭터 정보: 5분
- 성장 기록: 30분

외부 API 호출 횟수와 응답 시간을 줄이는 것이 목적입니다. 프로세스 메모리에 저장하는 단순한 방식이라 서버가 재시작되면 캐시도 초기화됩니다.

### 4. NEXON 직업 분류와 랭킹 조회 기준의 차이

캐릭터 기본 정보에서 받는 직업명과, 직업 랭킹을 조회할 때 `class` 파라미터로 쓰는 값이 서로 달랐습니다. 그래서 `static/jobs.json`에 직업명 → 랭킹 조회용 값 매핑을 두고, 서버가 캐릭터의 직업으로 조회 기준을 찾아서 직업 랭킹을 요청합니다. 매핑이 없거나 파일을 읽지 못하면 직업 랭킹 2종만 조회하지 않고, 나머지 정보는 정상적으로 표시합니다.

### 5. AI에게 계산을 맡기지 않기

위의 "데이터와 AI의 역할 분리"와 같은 문제 의식입니다. 계산 결과를 만들어서 넘기고, 응답은 후처리까지 거쳐서 화면에 보여줍니다.

### 6. Gemini 오류가 서비스 장애로 번지지 않도록 분리

AI 호출은 요청 제한이나 일시적인 오류가 날 수 있는 외부 의존성입니다.

- 캐릭터 조회와 성장 기록 조회가 끝난 뒤에 AI 리포트를 별도로 요청하기 때문에, AI가 실패해도 캐릭터 정보, 랭킹, 그래프는 그대로 표시됩니다.
- 요청 제한·일시 오류는 OpenRouter fallback으로 한 번 더 시도합니다.
- 그래도 실패하면 AI 리포트 영역에만 안내 메시지를 보여줍니다.

---

## 보안 / API Key 관리

- **API Key는 코드에 넣지 않고 환경변수로 관리합니다.** 코드에 직접 넣으면 GitHub에 올라가는 순간 외부에 노출되고, 한 번 공개된 키는 되돌리기 어렵기 때문입니다. 로컬에서는 `.env`(저장소에 포함하지 않음)를, Render에서는 Environment Variables를 사용합니다.
- 관리자 비밀번호는 해시(`ADMIN_PASSWORD_HASH`)로 설정할 수 있고, 로그인과 로그아웃 요청에는 CSRF 토큰 검증을 적용했습니다. 세션 쿠키는 `HttpOnly`, `SameSite=Lax`이며, HTTPS 배포 시 `FLASK_COOKIE_SECURE=true`로 Secure 속성을 켤 수 있습니다.
- 관리자 로그에는 행동 종류, 캐릭터명, 월드, 비교 대상, 성공/실패 여부만 저장합니다. 인증 정보나 요청 본문 전체는 저장하지 않습니다.
- 처리되지 않은 서버 오류는 상세 내용을 응답으로 내보내지 않고 일반 메시지만 반환합니다.

---

## 실행 방법

### 1. 프로젝트 클론

```bash
git clone https://github.com/mingming-01/maple-growth-tracker.git
cd maple-growth-tracker
```

### 2. 가상환경 생성 및 활성화

```bash
python -m venv .venv
```

Linux / macOS:

```bash
source .venv/bin/activate
```

Windows:

```bash
.venv\Scripts\activate
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. 환경변수 설정

프로젝트 루트에 `.env` 파일을 만듭니다.

```env
# 필수
NEXON_API_KEY=YOUR_NEXON_API_KEY

# AI (둘 중 하나 이상. 둘 다 있으면 Gemini 우선, 제한·일시 오류 시 OpenRouter)
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY
OPENROUTER_MODEL=openrouter/free

# 관리자 페이지 (설정하지 않으면 관리자 로그인을 사용할 수 없음)
ADMIN_USERNAME=YOUR_ADMIN_ID
ADMIN_PASSWORD_HASH=YOUR_PASSWORD_HASH

# 선택
FLASK_SECRET_KEY=RANDOM_SECRET
FLASK_COOKIE_SECURE=false
```

| 변수 | 설명 |
| --- | --- |
| `NEXON_API_KEY` | NEXON Open API 키 |
| `GEMINI_API_KEY` | Gemini API 키 |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | fallback용 OpenRouter 키 / 모델 (모델 기본값 `openrouter/free`) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH` | 관리자 계정. 해시 대신 `ADMIN_PASSWORD`(평문)도 코드상 지원하지만 해시를 권장 |
| `FLASK_SECRET_KEY` | 세션 서명 키. 없으면 실행할 때마다 임의로 생성되어 재시작 시 로그인 세션이 풀림 |
| `FLASK_COOKIE_SECURE` | `true`면 세션 쿠키에 Secure 속성 적용 (HTTPS 환경) |

- NEXON Open API는 NEXON_API_KEY가 필요합니다.
- AI 분석은 GEMINI_API_KEY 또는 OPENROUTER_API_KEY 중 하나 이상을 사용할 수 있습니다.
- 두 키가 모두 있으면 Gemini를 우선 사용하고, 제한·일시 오류 조건에서는 OpenRouter를 fallback으로 사용합니다.

### 5. 서버 실행

```bash
python app.py
```

```text
http://127.0.0.1:5000
```

`python app.py`는 `debug=True`, `0.0.0.0:5000`으로 실행되는 로컬 개발용 설정입니다.

---

## 배포

Render에 Flask 애플리케이션으로 배포했습니다.

- 서비스: https://maple-growth-tracker.onrender.com/
- `.env` 대신 Render의 Environment Variables에 위의 환경변수를 등록합니다. (`NEXON_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, 관리자 계정 관련 값 등)
- 관리자 로그는 instance/admin_logs.sqlite3에 SQLite로 저장합니다.

---

## 프로젝트에서 배운 점

- **외부 API는 느리고 실패할 수 있다는 전제로 설계해야 한다.** 병렬 조회와 캐시로 호출 비용을 줄이고, AI 같은 부가 기능이 실패해도 핵심 조회가 막히지 않도록 영역을 분리했습니다.
- **데이터의 의미를 먼저 이해해야 한다.** 레벨업 때 경험치가 초기화되는 게임 규칙을 처리하지 않으면 그래프, 평균, 예측이 모두 틀어집니다. 화면을 만들기 전에 데이터가 어떻게 변하는지 확인하는 것이 먼저였습니다.
- **AI는 역할을 좁힐수록 쓸 만해진다.** 계산은 코드로 하고 AI에게는 해석만 시키며, 응답은 후처리를 거쳐 보여주는 구조로 만들었습니다.
- **운영 관점의 기본기.** API Key 관리, 관리자 인증과 CSRF, 로그에 남길 정보의 범위, 오류 메시지 노출 범위를 고민하면서 "동작하는 것"과 "운영할 수 있는 것"의 차이를 배웠습니다.

---

## 알아둘 점

- NEXON Open API가 제공하는 데이터와 정책에 따라 조회 가능한 정보가 달라질 수 있습니다.
- NEXON Open API, Gemini API(또는 OpenRouter)를 쓰려면 각각의 API Key가 필요하고, 사용량 한도가 적용될 수 있습니다.
- 성장 예측은 최근 평균 성장량이 유지된다는 가정의 예상치입니다.
- API Key 등 민감한 정보는 환경변수로 관리하고, 공개 저장소에 올리지 마세요.
