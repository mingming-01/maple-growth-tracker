# Maple Growth Tracker

메이플스토리 캐릭터의 성장 데이터를 조회하고,
최근 경험치와 랭킹 변화를 시각화하며 Gemini AI를 활용해 성장 패턴을 분석하는 웹 애플리케이션입니다.

<p align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square\&logo=python\&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square\&logo=flask\&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square\&logo=javascript\&logoColor=black)
![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?style=flat-square\&logo=chart.js\&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini%20API-4285F4?style=flat-square\&logo=google\&logoColor=white)

</p>

---

## ✨ 프로젝트 소개

캐릭터명을 입력하면 NEXON Open API를 통해 캐릭터 정보를 조회합니다.

조회한 데이터를 기반으로 최근 7일간의 성장 기록을 정리하고, 경험치와 랭킹 변화를 차트와 표로 확인할 수 있도록 구현했습니다.

또한 Gemini API를 활용하여 수치 데이터에서 확인되는 성장 패턴을 자연어로 분석합니다.

전체적인 데이터 흐름은 다음과 같습니다.

**데이터 수집 → 데이터 가공 → 시각화 → AI 분석**

단순히 API 데이터를 보여주는 것보다, 수집한 데이터를 사용자가 이해하기 쉬운 형태로 정리하고 해석하는 것에 중점을 두었습니다.

---

## 🚀 주요 기능

### 캐릭터 정보

* 캐릭터명
* 월드
* 직업
* 길드
* 현재 레벨
* 경험치 진행률
* 최근 일일 평균 경험치

### 랭킹

* 전체 랭킹
* 월드 랭킹
* 직업 랭킹
* 직업 + 월드 랭킹

### 성장 분석

최근 7일간의 데이터를 기반으로 성장 흐름을 확인할 수 있습니다.

* 일자별 레벨
* 경험치 변화
* 일일 경험치 증가량
* 월드 랭킹 변화
* 레벨업 여부
* 최근 성장 기록

### 성장 그래프

Chart.js를 활용하여 성장 데이터를 시각화합니다.

* 경험치 누적 성장 그래프
* 레벨업 시점 표시
* 레벨업 이전 레벨 → 현재 레벨 표시
* 날짜별 성장 흐름 확인

### 성장 예측

현재 경험치 진행률과 최근 성장 데이터를 기반으로 다음 레벨까지의 성장 정보를 제공합니다.

레벨업 직후처럼 경험치 진행률이 매우 낮은 경우에는 부정확한 예측을 방지하기 위해 예측값을 표시하지 않습니다.

### 이미지 / PDF 저장

조회한 성장 분석 결과를 이미지 또는 PDF 형태로 저장할 수 있습니다.

---

## 🤖 AI 성장 판독

Gemini API를 활용하여 최근 7일간의 성장 데이터를 분석합니다.

AI는 다음 항목을 제공합니다.

* 성장 패턴
* 성장 분석
* 레벨업
* AI 판단

AI가 실제 데이터에 없는 내용을 추측하지 않도록 **데이터 처리와 AI 분석의 역할을 분리**했습니다.

```text
NEXON Open API
       ↓
캐릭터 및 랭킹 데이터
       ↓
      Flask
       ↓
데이터 조회 및 가공
       ↓
최근 7일 성장 데이터
       ↓
    Gemini API
       ↓
  AI 성장 판독
       ↓
      Web UI
```

### 역할 분리

| 역할          | 담당                      |
| ----------- | ----------------------- |
| 게임 데이터 수집   | NEXON Open API          |
| 데이터 조회 및 가공 | Flask / Python          |
| 경험치 증가량 계산  | Python                  |
| 레벨업 판단      | Python                  |
| 데이터 시각화     | Chart.js                |
| 성장 패턴 분석    | Gemini API              |
| 화면 구성       | HTML / CSS / JavaScript |

---

## 🛠 기술 스택

| 구분                 | 기술                    |
| ------------------ | --------------------- |
| Backend            | Python, Flask         |
| Frontend           | HTML, CSS, JavaScript |
| Data Visualization | Chart.js              |
| AI                 | Google Gemini API     |
| Game Data          | NEXON Open API        |
| Export             | html2canvas, jsPDF    |
| Deployment         | Render                |
| Environment        | Kali Linux, VS Code   |
| Version Control    | Git, GitHub           |

---

## 📁 프로젝트 구조

```text
maple-growth-tracker/
│
├── app.py
├── requirements.txt
├── .gitignore
├── README.md
│
├── templates/
│   └── index.html
│
└── static/
    ├── app.js
    ├── style.css
    └── jobs.json
```

### 주요 파일

| 파일                     | 역할                |
| ---------------------- | ----------------- |
| `app.py`               | Flask 서버 및 API 처리 |
| `requirements.txt`     | Python 패키지 관리     |
| `templates/index.html` | 웹 페이지 구조          |
| `static/app.js`        | 사용자 동작 및 데이터 렌더링  |
| `static/style.css`     | 웹 페이지 디자인         |
| `static/jobs.json`     | 직업 그룹 및 직업 매핑     |
| `.gitignore`           | 환경변수 및 가상환경 제외    |

---

## ⚙️ 실행 방법

### 1. 프로젝트 클론

```bash
git clone https://github.com/mingming-01/maple-growth-tracker.git
cd maple-growth-tracker
```

### 2. 가상환경 생성

```bash
python -m venv .venv
```

### 3. 가상환경 활성화

Linux / macOS:

```bash
source .venv/bin/activate
```

Windows:

```bash
.venv\Scripts\activate
```

### 4. 패키지 설치

```bash
pip install -r requirements.txt
```

### 5. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성합니다.

```env
NEXON_API_KEY=YOUR_NEXON_API_KEY
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

### 6. 서버 실행

```bash
python app.py
```

브라우저에서 접속합니다.

```text
http://127.0.0.1:5000
```

---

## 🌐 배포

Render를 이용하여 Flask 애플리케이션을 배포했습니다.

**서비스**

https://maple-growth-tracker.onrender.com/

**GitHub**

https://github.com/mingming-01/maple-growth-tracker

배포 환경에서는 `.env` 파일 대신 Render의 Environment Variables에 다음 값을 등록합니다.

```text
NEXON_API_KEY
GEMINI_API_KEY
```

API Key는 GitHub 저장소에 직접 저장하지 않고 환경변수로 관리합니다.

---

## 🧩 주요 문제 해결

### 레벨업 시 경험치 그래프 급락

메이플스토리는 레벨업 시 새로운 레벨의 경험치 값이 이전 레벨의 경험치보다 작아질 수 있습니다.

단순히 날짜별 경험치 차이를 계산하면 레벨업 시점에서 경험치가 크게 감소한 것처럼 보이는 문제가 발생했습니다.

이를 해결하기 위해 레벨업 여부를 먼저 판단하고, 성장 그래프에서는 레벨업 시점을 별도로 처리했습니다.

### API 호출 최적화

동일한 데이터를 반복해서 요청하는 것을 줄이기 위해 캐시를 적용했습니다.

* 캐릭터 정보: 5분
* 성장 기록: 30분

또한 여러 랭킹 데이터를 병렬로 조회하여 API 응답 시간을 줄였습니다.

### 직업 데이터 처리

NEXON API에서 제공하는 직업 분류와 검색 화면에서 사용하는 직업 분류가 일치하지 않는 문제를 해결하기 위해 별도의 직업 매핑 데이터를 구성했습니다.

`jobs.json`을 이용하여 캐릭터 직업과 NEXON 랭킹 조회 기준을 연결했습니다.

### AI 분석의 근거 제한

Gemini가 실제 데이터에 없는 내용을 생성하는 문제를 줄이기 위해 분석 규칙을 명확하게 정의했습니다.

AI는 제공된 성장 데이터를 해석하는 역할을 담당하고, 실제 데이터 계산과 레벨업 판단은 애플리케이션에서 처리하도록 구성했습니다.

---

## 💡 개발 포인트

이 프로젝트에서는 외부 API와 AI API를 단순히 연결하는 것보다 **수집한 데이터를 어떻게 사용자에게 의미 있는 정보로 전달할 것인지**에 중점을 두었습니다.

특히 다음과 같은 역할을 명확하게 분리했습니다.

```text
API
↓
원본 데이터 수집

Python
↓
데이터 가공 및 판단

Chart.js
↓
데이터 시각화

Gemini
↓
성장 데이터 해석
```

이를 통해 데이터의 계산과 판단은 애플리케이션에서 처리하고, AI는 이미 정리된 데이터를 해석하는 역할에 집중하도록 구성했습니다.

---

## ⚠️ 주의사항

NEXON Open API에서 제공하는 데이터와 정책에 따라 조회 가능한 정보 및 기능이 달라질 수 있습니다.

NEXON Open API와 Google Gemini API를 사용하기 위해 각각의 API Key가 필요합니다.

API Key와 같은 민감한 정보는 반드시 환경변수로 관리하고 공개 저장소에 업로드하지 않아야 합니다.
