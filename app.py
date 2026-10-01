from flask import Flask, jsonify, request, render_template, redirect, url_for, session
from functools import wraps
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import requests
from dotenv import load_dotenv
from google import genai


load_dotenv()

app = Flask(__name__)
app.json.ensure_ascii = False
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("FLASK_COOKIE_SECURE", "").lower() == "true"
)


# Nexon Open API
API_KEY = os.getenv("NEXON_API_KEY")
BASE_URL = "https://open.api.nexon.com/maplestory/v1"
HEADERS = {"x-nxopen-api-key": API_KEY}


# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


# 관리자 인증 및 감사 로그
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
LOG_DB_PATH = os.path.join(app.instance_path, "admin_logs.sqlite3")
os.makedirs(app.instance_path, exist_ok=True)


def initialize_log_db():
    with sqlite3.connect(LOG_DB_PATH, timeout=5) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                action TEXT NOT NULL,
                character_name TEXT,
                world_name TEXT,
                comparison_name TEXT,
                result TEXT NOT NULL
            )
        """)


def log_action(action, character_name=None, world_name=None, result="성공", comparison_name=None):
    """사용자 행동의 최소 정보만 관리자 로그 데이터베이스에 남긴다."""
    try:
        with sqlite3.connect(LOG_DB_PATH, timeout=5) as connection:
            connection.execute(
                """
                INSERT INTO action_logs
                    (created_at, action, character_name, world_name, comparison_name, result)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().astimezone().isoformat(timespec="seconds"),
                    action,
                    character_name,
                    world_name,
                    comparison_name,
                    result
                )
            )
    except sqlite3.Error:
        # 로그 저장 문제로 사용자 요청이 실패하지 않도록 상세 데이터는 남기지 않는다.
        print("관리자 로그 저장에 실패했습니다.")


initialize_log_db()


# 간단한 메모리 캐시
CACHE = {}
CHARACTER_CACHE_TTL = 300
HISTORY_CACHE_TTL = 1800


def get_cache(key):
    item = CACHE.get(key)
    if not item:
        return None
    if time.time() - item["time"] > item["ttl"]:
        del CACHE[key]
        return None
    return item["data"]


def set_cache(key, data, ttl):
    CACHE[key] = {"time": time.time(), "data": data, "ttl": ttl}


def get_ocid(character_name):
    response = requests.get(
        f"{BASE_URL}/id",
        headers=HEADERS,
        params={"character_name": character_name}
    )
    if response.status_code != 200:
        return None, response
    return response.json()["ocid"], response


def get_basic_character(ocid):
    response = requests.get(
        f"{BASE_URL}/character/basic",
        headers=HEADERS,
        params={"ocid": ocid}
    )
    if response.status_code != 200:
        return None, response
    return response.json(), response


def get_ranking(target_date, world_name=None, ocid=None, character_class=None):
    params = {"date": target_date, "world_type": 0, "page": 1}
    if world_name:
        params["world_name"] = world_name
    if character_class:
        params["class"] = character_class
    if ocid:
        params["ocid"] = ocid

    response = requests.get(
        f"{BASE_URL}/ranking/overall",
        headers=HEADERS,
        params=params
    )
    if response.status_code != 200:
        return None, response
    ranking_list = response.json().get("ranking", [])
    if not ranking_list:
        return None, response
    return ranking_list[0], response


def get_api_class(character_class):
    jobs_path = os.path.join(app.root_path, "static", "jobs.json")
    try:
        with open(jobs_path, "r", encoding="utf-8") as file:
            jobs_data = json.load(file)
    except Exception:
        print("jobs.json 로드에 실패했습니다.")
        return None
    return jobs_data.get(character_class)


def get_character_rankings(target_date, world_name, character_class, ocid):
    result = {
        "ranking": None,
        "worldRanking": None,
        "jobWorldRanking": None,
        "jobRanking": None
    }
    api_class = get_api_class(character_class)

    def fetch_overall():
        return get_ranking(target_date=target_date, ocid=ocid)

    def fetch_world():
        return get_ranking(target_date=target_date, world_name=world_name, ocid=ocid)

    def fetch_job_world():
        if not api_class:
            return None, None
        return get_ranking(
            target_date=target_date,
            world_name=world_name,
            character_class=api_class,
            ocid=ocid
        )

    def fetch_job():
        if not api_class:
            return None, None
        return get_ranking(
            target_date=target_date,
            character_class=api_class,
            ocid=ocid
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(fetch_overall),
            executor.submit(fetch_world),
            executor.submit(fetch_job_world),
            executor.submit(fetch_job)
        ]
        overall_data, _ = futures[0].result()
        world_data, _ = futures[1].result()
        job_world_data, _ = futures[2].result()
        job_data, _ = futures[3].result()

    if overall_data:
        result["ranking"] = overall_data.get("ranking")
    if world_data:
        result["worldRanking"] = world_data.get("ranking")
    if job_world_data:
        result["jobWorldRanking"] = job_world_data.get("ranking")
    if job_data:
        result["jobRanking"] = job_data.get("ranking")
    return result


def sanitize_ai_text(value, expected_date=None):
    """모델 응답의 마크다운과 내부 표현을 정리해 일반 문장만 화면에 전달한다."""
    text = str(value or "")
    text = re.sub(r"```[\w-]*", "", text)
    text = re.sub(r"(?m)^\s*[-*_]{3,}\s*$", "", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    text = re.sub(r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    internal_terms = {
        r"\bmetrics\.prediction\b": "성장 전망",
        r"\brankingChange\b": "랭킹 변화",
        r"\bvalidGrowthDays\b": "성장 기록",
        r"\brecordedDays\b": "기록된 날짜",
        r"\blatestDailyGrowth\b": "최근 성장 흐름",
        r"\baverageDailyGrowth\b": "평균 성장 흐름",
        r"\bhighestDailyGrowth\b": "높은 성장 기록",
        r"\blowestDailyGrowth\b": "낮은 성장 기록",
        r"\bsevenDayGrowth\b": "최근 성장 기록",
        r"\bgrowthComparison\b": "성장 흐름 비교",
        r"\bearlierAverage\b": "이전 성장 흐름",
        r"\brecentAverage\b": "최근 성장 흐름",
        r"\blevelUps\b": "레벨업 기록",
        r"\bestimatedDays\b": "예상 기간",
        r"\bestimatedDate\b": "예상 날짜",
        r"\brequiredExperience\b": "필요 경험치",
        r"\binsufficient_data\b": "기록 부족",
        r"\bincreased\b": "증가한 흐름",
        r"\bdecreased\b": "감소한 흐름",
        r"\bstable\b": "일정한 흐름",
        r"\bnull\b|\bundefined\b": "확인되지 않음"
    }
    for pattern, replacement in internal_terms.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 긴 원본 경험치가 그대로 노출되는 것을 막는다.
    text = re.sub(
        r"\(?\s*(?:\d{1,3}(?:,\d{3}){2,}|\d{10,})(?:\.\d+)?\s*\)?",
        "해당 경험치 수치",
        text
    )

    # 화면의 예측 카드와 동일한 계산 날짜를 사용해 AI가 다른 날짜를 말하지 않게 한다.
    if expected_date:
        try:
            prediction_date = date.fromisoformat(str(expected_date))
            date_label = f"{prediction_date.month}월 {prediction_date.day}일"
            date_patterns = (
                r"\b\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일",
                r"\b\d{1,2}\s*월\s*\d{1,2}\s*일",
                r"\b\d{4}-\d{1,2}-\d{1,2}\b",
                r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b"
            )
            for pattern in date_patterns:
                text = re.sub(pattern, date_label, text)
        except (TypeError, ValueError):
            pass

    text = re.sub(r"[*_~`]", "", text)
    text = re.sub(r"(?m)^\s*#+\s*", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# 메인 화면
@app.route("/")
def home():
    return render_template("index.html")


# 관리자 로그인 및 로그 조회
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_authenticated"):
        return redirect(url_for("admin_logs"))

    csrf_token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    error = None
    if request.method == "POST":
        submitted_token = request.form.get("csrf_token", "")
        valid_token = hmac.compare_digest(str(csrf_token), str(submitted_token))
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        password_valid = False
        if ADMIN_PASSWORD_HASH:
            try:
                password_valid = check_password_hash(ADMIN_PASSWORD_HASH, password)
            except (ValueError, TypeError):
                password_valid = False
        elif ADMIN_PASSWORD:
            password_valid = hmac.compare_digest(ADMIN_PASSWORD, password)

        if not ADMIN_USERNAME or not (ADMIN_PASSWORD_HASH or ADMIN_PASSWORD):
            error = "관리자 인증 환경변수가 설정되지 않았습니다."
        elif valid_token and hmac.compare_digest(ADMIN_USERNAME, username) and password_valid:
            session.clear()
            session["admin_authenticated"] = True
            session["csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("admin_logs"))
        else:
            error = "아이디 또는 비밀번호를 확인해주세요."

    return render_template(
        "admin_login.html",
        csrf_token=csrf_token,
        error=error,
        configured=bool(ADMIN_USERNAME and (ADMIN_PASSWORD_HASH or ADMIN_PASSWORD))
    )


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped_view


@app.route("/admin/logs")
@admin_required
def admin_logs():
    with sqlite3.connect(LOG_DB_PATH, timeout=5) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT created_at, action, character_name, world_name, comparison_name, result "
            "FROM action_logs ORDER BY id DESC LIMIT 500"
        ).fetchall()
    return render_template(
        "admin_logs.html",
        logs=rows,
        csrf_token=session.setdefault("csrf_token", secrets.token_urlsafe(32))
    )


@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    submitted_token = request.form.get("csrf_token", "")
    expected_token = session.get("csrf_token", "")
    if not hmac.compare_digest(str(expected_token), str(submitted_token)):
        return "잘못된 요청입니다.", 400
    session.clear()
    return redirect(url_for("admin_login"))


# 월드와 직업 목록 조회
@app.route("/api/options")
def get_options():
    today = date.today().strftime("%Y-%m-%d")
    response = requests.get(
        f"{BASE_URL}/ranking/overall",
        headers=HEADERS,
        params={"date": today, "world_type": 0, "page": 1}
    )
    if response.status_code != 200:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        return jsonify({"error": "서버 및 직업 목록을 가져오지 못했습니다.", "detail": detail}), response.status_code

    ranking_list = response.json().get("ranking", [])
    worlds = set()
    classes = {}
    for character in ranking_list:
        world_name = character.get("world_name")
        class_name = character.get("class_name")
        sub_class_name = character.get("sub_class_name")
        if world_name:
            worlds.add(world_name)
        if class_name:
            classes.setdefault(class_name, set())
            if sub_class_name:
                classes[class_name].add(sub_class_name)
    class_data = {name: sorted(jobs) for name, jobs in classes.items()}
    return jsonify({"worlds": sorted(worlds), "classes": dict(sorted(class_data.items()))})


# 캐릭터 정보와 현재 랭킹 조회
@app.route("/api/character")
def get_character():
    character_name = request.args.get("name", "").strip()
    if not character_name:
        return jsonify({"error": "캐릭터 이름을 입력해주세요."}), 400

    cache_key = f"character:{character_name}"
    cached_character = get_cache(cache_key)
    if cached_character is not None:
        return jsonify(cached_character)

    ocid, response = get_ocid(character_name)
    if not ocid:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        return jsonify({"error": "캐릭터 정보를 찾을 수 없습니다.", "detail": detail}), response.status_code

    basic, response = get_basic_character(ocid)
    if not basic:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        return jsonify({"error": "캐릭터 기본 정보를 가져오지 못했습니다.", "detail": detail}), response.status_code

    character_class = basic["character_class"]
    character_rankings = get_character_rankings(
        target_date=datetime.now().strftime("%Y-%m-%d"),
        world_name=basic["world_name"],
        character_class=character_class,
        ocid=ocid
    )
    result = {
        "characterName": basic["character_name"],
        "character_image": basic.get("character_image"),
        "worldName": basic["world_name"],
        "job": character_class,
        "guildName": basic.get("character_guild_name"),
        "level": basic["character_level"],
        "experience": basic["character_exp"],
        "experienceRate": basic["character_exp_rate"],
        "ranking": character_rankings["ranking"],
        "worldRanking": character_rankings["worldRanking"],
        "jobWorldRanking": character_rankings["jobWorldRanking"],
        "jobRanking": character_rankings["jobRanking"],
        "rankingExperience": basic["character_exp"],
        "ocid": ocid
    }
    set_cache(cache_key, result, CHARACTER_CACHE_TTL)
    return jsonify(result)


# 최근 7일 성장 기록 조회 및 변화량 계산
@app.route("/api/history")
def get_history():
    character_name = request.args.get("name", "").strip()
    if not character_name:
        return jsonify({"error": "캐릭터 이름을 입력해주세요."}), 400

    cache_key = f"history:{character_name}"
    cached_history = get_cache(cache_key)
    if cached_history is not None:
        return jsonify(cached_history)

    ocid, response = get_ocid(character_name)
    if not ocid:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        return jsonify({"error": "캐릭터 정보를 찾을 수 없습니다.", "detail": detail}), response.status_code

    basic, response = get_basic_character(ocid)
    if not basic:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        return jsonify({"error": "캐릭터 정보를 가져오지 못했습니다.", "detail": detail}), response.status_code

    world_name = basic["world_name"]
    today = date.today()

    def fetch_history(target_date):
        date_string = target_date.strftime("%Y-%m-%d")
        ranking_data, _ = get_ranking(
            target_date=date_string,
            world_name=world_name,
            ocid=ocid
        )
        if ranking_data:
            return {
                "date": date_string,
                "ranking": ranking_data.get("ranking"),
                "level": ranking_data.get("character_level"),
                "experience": ranking_data.get("character_exp")
            }
        return {"date": date_string, "ranking": None, "level": None, "experience": None}

    dates = [today - timedelta(days=i) for i in range(7)]
    with ThreadPoolExecutor(max_workers=7) as executor:
        history = list(executor.map(fetch_history, dates))
    history.reverse()

    for index, current in enumerate(history):
        if index == 0:
            current["experienceChange"] = None
            current["rankingChange"] = None
            continue
        previous = history[index - 1]
        current["levelUp"] = False
        if current["experience"] is not None and previous["experience"] is not None:
            if (
                current["level"] is not None
                and previous["level"] is not None
                and current["level"] > previous["level"]
            ):
                current["experienceChange"] = None
                current["levelUp"] = True
            else:
                current["experienceChange"] = current["experience"] - previous["experience"]
        else:
            current["experienceChange"] = None

        if current["ranking"] is not None and previous["ranking"] is not None:
            current["rankingChange"] = previous["ranking"] - current["ranking"]
        else:
            current["rankingChange"] = None

    experience_changes = [
        item["experienceChange"]
        for item in history
        if item.get("experienceChange") is not None
    ]
    average_experience = sum(experience_changes) / len(experience_changes) if experience_changes else None
    result = {
        "characterName": basic["character_name"],
        "worldName": world_name,
        "level": basic["character_level"],
        "history": history,
        "averageDailyExperience": average_experience
    }
    set_cache(cache_key, result, HISTORY_CACHE_TTL)
    return jsonify(result)


def generate_ai_analysis(character, history, computed_metrics=None):
    if not gemini_client:
        return {"error": "Gemini API 키가 설정되지 않았습니다."}

    growth_data = [
        {
            "date": item.get("date"),
            "level": item.get("level"),
            "experienceChange": item.get("experienceChange"),
            "ranking": item.get("ranking"),
            "rankingChange": item.get("rankingChange"),
            "levelUp": item.get("levelUp", False)
        }
        for item in history
    ]

    if computed_metrics is not None:
        # 프런트엔드에서 이미 계산한 지표를 Gemini에 전달하고 숫자 계산은 맡기지 않는다.
        prediction = computed_metrics.get("prediction")
        prediction_date = prediction.get("estimatedDate") if isinstance(prediction, dict) else None
        prediction_date_label = None
        if prediction_date:
            try:
                parsed_prediction_date = date.fromisoformat(str(prediction_date))
                prediction_date_label = f"{parsed_prediction_date.month}월 {parsed_prediction_date.day}일"
            except (TypeError, ValueError):
                prediction_date_label = None

        source_data = {
            "character": {
                "name": character.get("characterName"),
                "world": character.get("worldName"),
                "job": character.get("job"),
                "level": character.get("level"),
                "experienceRate": character.get("experienceRate")
            },
            "metrics": computed_metrics,
            "predictionDisplayDate": prediction_date_label,
            "history": growth_data
        }
        prompt = f"""
너는 메이플스토리 캐릭터의 성장 과정을 해석하는 도우미야.
아래 데이터는 앱에서 계산했거나 API에서 가져온 사실이야. 새 숫자를 계산하거나 추정하지 말고, 사실을 반복해서 나열하기보다 변화의 특징과 의미를 설명해.
성장 요약과 전망 카드에 이미 숫자가 있으므로 레벨, 경험치, 평균·최고·최저 성장량, 랭킹, 소요일 등의 숫자를 리포트에서 되풀이하지 마. 긴 숫자나 괄호 속 원본 수치도 쓰지 마.
성장 전망에서 날짜를 언급할 때는 predictionDisplayDate 값을 그대로 사용해. 그 날짜를 다시 계산하거나 다른 날짜로 바꾸지 마. 날짜 값이 없으면 날짜를 만들어내지 마.
기록이 부족하거나 값이 확인되지 않으면 판단하기 어렵다고 자연스럽게 말해. 데이터 부족을 감추거나 없는 사실을 채워 넣지 마.
성장 흐름은 기록이 충분히 뒷받침할 때만 해석하고, 레벨업은 기록에서 확인될 때만 언급해. 플레이 방식이나 시간은 추측하지 마.
개발용 키 이름, 영어 상태값, null, undefined를 답변에 쓰지 마.
마크다운 없이 일반 문장만 작성해. 제목 기호, 굵게·기울임 표시, 글머리표, 번호 목록, 수평선, 백틱, 코드 블록은 쓰지 마.
아래 다섯 구분 표시는 정확히 그대로 사용하고, 각 항목은 최대 두 개의 짧은 문장으로 작성해. 구분 표시 이외의 제목이나 목록은 추가하지 마.

데이터:
{json.dumps(source_data, ensure_ascii=False)}

[성장 패턴]
[성장 변화]
[레벨업 분석]
[성장 전망]
[AI 코멘트]
"""
    else:
        # 기존 GET 방식 호출 호환성을 유지하며 애플리케이션이 준 기록만 해석한다.
        prompt = f"""
너는 메이플스토리 캐릭터의 성장 데이터를 해석하는 도우미야.
제공된 사실만 이용하고 경험치, 평균, 추세, 예측 날짜 등 숫자를 새로 계산하거나 미래를 추정하지 마.
기록이 부족한 경우 데이터 부족을 밝히고, 근거 없는 행동이나 플레이 스타일을 추측하지 마.
화면에 수치가 별도로 표시되므로 원본 숫자를 나열하지 말고 흐름의 특징을 간결하게 설명해.
마크다운 없이 일반 한국어 문장만 작성하고 개발용 키 이름, 영어 상태값, null, undefined를 답변에 쓰지 마.
아래 네 구분 표시는 그대로 사용해.
[성장 패턴]
[성장 분석]
[레벨업]
[AI 판단]

캐릭터:
{character.get("characterName")} / {character.get("worldName")} / Lv.{character.get("level")}
최근 성장 기록:
{json.dumps(growth_data, ensure_ascii=False)}
"""

    try:
        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )
        expected_date = None
        if computed_metrics is not None:
            prediction = computed_metrics.get("prediction")
            if isinstance(prediction, dict):
                expected_date = prediction.get("estimatedDate")
        return {"analysis": sanitize_ai_text(response.text or "분석 결과가 비어 있습니다.", expected_date)}
    except Exception as error:
        print(f"Gemini 성장 분석 요청에 실패했습니다: {error}")
        return {"error": "AI 분석을 불러오지 못했습니다."}


@app.route("/api/ai-analysis", methods=["GET", "POST"])
def ai_analysis():
    character_name = request.args.get("name", "").strip()
    if not character_name:
        return jsonify({"error": "캐릭터명을 입력해주세요."}), 400

    try:
        character_response = get_character()
        if character_response.status_code != 200:
            return jsonify({"error": "캐릭터 정보를 불러오지 못했습니다."}), character_response.status_code
        character = character_response.get_json()
        request.environ["maple_character_context"] = character

        history_response = get_history()
        if history_response.status_code != 200:
            return jsonify({"error": "성장 기록을 불러오지 못했습니다."}), history_response.status_code
        history_data = history_response.get_json()
        metrics = None
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            metrics = payload.get("metrics")
            if not isinstance(metrics, dict):
                return jsonify({"error": "계산된 성장 지표가 필요합니다."}), 400

        result = generate_ai_analysis(character, history_data.get("history", []), metrics)
        if "error" in result:
            return jsonify(result), 500
        return jsonify(result)
    except Exception as error:
        print(f"Gemini AI 분석 API 요청에 실패했습니다: {error}")
        return {"error": "AI 분석을 불러오지 못했습니다."}


def generate_ai_comparison(primary, comparison):
    if not gemini_client:
        return {"error": "Gemini API 키가 설정되지 않았습니다."}

    prompt_data = {"primary": primary, "comparison": comparison}
    prompt = f"""
너는 두 메이플스토리 캐릭터의 성장 흐름 차이를 설명하는 도우미야.
아래 지표는 앱이 같은 기준으로 계산했어. 어떤 수도 직접 계산하거나 다시 예측하지 마.
비교 카드에 숫자가 표시되므로 숫자와 순위를 반복하지 말고, 두 캐릭터의 최근 성장 변화, 흐름의 안정성, 순위 변화와 성장의 관계에서 실제로 확인되는 차이를 해석해.
기록이 충분하지 않으면 그 비교는 어렵다고 자연스럽게 알려. 현재 레벨만으로 우위를 단정하거나 행동 방식·플레이 시간을 추측하지 마.
마크다운, 제목, 번호, 글머리표, 굵게 표시, 코드 표현, 원본 수치 없이 자연스러운 한국어 2~4문장으로 작성해.
개발용 키 이름, 영어 상태값, null, undefined는 답변에 절대 쓰지 마. 예측 날짜나 새 수치를 만들어내지 마.

비교 데이터:
{json.dumps(prompt_data, ensure_ascii=False)}
"""
    try:
        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )
        return {"analysis": sanitize_ai_text(response.text or "비교 분석 결과가 비어 있습니다.")}
    except Exception as error:
        print(f"Gemini 성장 분석 요청에 실패했습니다: {error}")
        return {"error": "AI 성장 분석을 불러오지 못했습니다."}


@app.route("/api/ai-comparison", methods=["POST"])
def ai_comparison():
    payload = request.get_json(silent=True) or {}
    primary = payload.get("primary")
    comparison = payload.get("comparison")
    if not isinstance(primary, dict) or not isinstance(comparison, dict):
        return jsonify({"error": "두 캐릭터의 성장 데이터가 필요합니다."}), 400

    for subject in (primary, comparison):
        if not isinstance(subject.get("character"), dict) or not isinstance(subject.get("metrics"), dict):
            return jsonify({"error": "캐릭터 정보와 계산된 성장 지표가 필요합니다."}), 400
        if not subject["character"].get("characterName"):
            return jsonify({"error": "캐릭터명을 확인할 수 없습니다."}), 400

    first_name = primary["character"]["characterName"].strip().casefold()
    second_name = comparison["character"]["characterName"].strip().casefold()
    if first_name == second_name:
        return jsonify({"error": "같은 캐릭터는 비교할 수 없습니다."}), 400

    result = generate_ai_comparison(primary, comparison)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@app.after_request
def record_user_action(response):
    """인증 정보나 전체 요청 본문은 저장하지 않고 지정된 행동만 기록한다."""
    endpoint = request.endpoint
    status = "성공" if 200 <= response.status_code < 400 else "실패"

    if endpoint == "get_character":
        name = request.args.get("name", "").strip() or None
        data = response.get_json(silent=True) or {}
        log_action(
            "캐릭터 조회",
            character_name=data.get("characterName") or name,
            world_name=data.get("worldName"),
            result=status
        )
    elif endpoint == "ai_analysis":
        name = request.args.get("name", "").strip() or None
        character = request.environ.get("maple_character_context", {})
        log_action(
            "AI 성장 분석",
            character_name=character.get("characterName") or name,
            world_name=character.get("worldName"),
            result=status
        )
    elif endpoint == "ai_comparison":
        payload = request.get_json(silent=True) or {}
        primary = payload.get("primary", {}).get("character", {}) if isinstance(payload.get("primary"), dict) else {}
        comparison = payload.get("comparison", {}).get("character", {}) if isinstance(payload.get("comparison"), dict) else {}
        log_action(
            "캐릭터 비교",
            character_name=primary.get("characterName"),
            world_name=primary.get("worldName"),
            comparison_name=comparison.get("characterName"),
            result=status
        )

    if response.status_code >= 500:
        log_action("서비스 오류", result="실패")
    return response


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return error
    # 예외 메시지나 요청 헤더에는 민감정보가 포함될 수 있어 로그로 남기지 않는다.
    print("처리되지 않은 서버 오류가 발생했습니다.")
    return jsonify({"error": "서버에서 요청을 처리하지 못했습니다."}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)