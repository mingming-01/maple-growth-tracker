from flask import jsonify, request, render_template, redirect, url_for, session, current_app, has_app_context
from functools import wraps
from werkzeug.exceptions import HTTPException
import hashlib
import os
import re
import sqlite3
import time
from datetime import date, datetime, timedelta
from threading import Lock
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row
from tracker.repositories.growth_history_store import GrowthHistoryStore
from tracker.services.growth_history_service import GrowthHistoryService
from tracker.services.admin_log_service import admin_required, format_admin_log_time
from tracker.repositories.api_snapshot_repository import (
    initialize_snapshot_db as initialize_snapshot_db_for_path,
    save_api_snapshot as save_api_snapshot_for_path,
    load_api_snapshot as load_api_snapshot_for_path,
)
from google import genai
from google.genai import types


# 변경되지 않는 도메인 상수만 모듈 상수로 유지한다.
KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")
HISTORY_BACKFILL_BATCH_SIZE = 10
CHARACTER_CACHE_TTL = 300
HISTORY_CACHE_TTL = 1800
AI_RESPONSE_CACHE_TTL = 6 * 60 * 60
AI_RESPONSE_CACHE_MAX_ENTRIES = 100
RUNTIME_CACHE_MAX_ENTRIES = 1000


class RuntimeState:
    """Flask 앱 인스턴스마다 독립적으로 보유하는 런타임 의존성."""

    def __init__(self, flask_app=None):
        config = flask_app.config if flask_app is not None else {}
        instance_path = (
            flask_app.instance_path if flask_app is not None
            else os.path.abspath("instance")
        )
        self.nexon_api_key = config.get("NEXON_API_KEY", "")
        self.gemini_api_key = config.get("GEMINI_API_KEY", "")
        try:
            ai_timeout_ms = max(1000, int(float(config.get("AI_API_TIMEOUT", 30)) * 1000))
        except (TypeError, ValueError):
            ai_timeout_ms = 30000
        self.gemini_client = (
            genai.Client(
                api_key=self.gemini_api_key,
                http_options=types.HttpOptions(timeout=ai_timeout_ms),
            )
            if self.gemini_api_key else None
        )
        self.openrouter_api_key = config.get("OPENROUTER_API_KEY", "")
        self.openrouter_model = config.get("OPENROUTER_MODEL", "openrouter/free")
        self.admin_username = config.get("ADMIN_USERNAME", "")
        self.admin_password_hash = config.get("ADMIN_PASSWORD_HASH", "")
        self.admin_password = config.get("ADMIN_PASSWORD", "")
        self.ai_api_retries = config.get("AI_API_RETRIES", 1)
        self.ai_api_retry_backoff = config.get("AI_API_RETRY_BACKOFF", 0.5)
        self.growth_database_url = config.get("GROWTH_DATABASE_URL", "").strip()
        self.log_db_backend = (
            "postgres"
            if self.growth_database_url.startswith(("postgres://", "postgresql://"))
            else "sqlite"
        )
        self.log_storage_warning = ""
        self.log_db_path = os.path.join(instance_path, "admin_logs.sqlite3")
        self.snapshot_db_path = os.path.join(instance_path, "growth_snapshots.sqlite3")
        self.snapshot_db_backend = "postgres" if self.growth_database_url.startswith(("postgres://", "postgresql://")) else "sqlite"
        self.snapshot_storage_warning = ""
        self.growth_history_repository = GrowthHistoryStore(
            database_url=self.growth_database_url,
            sqlite_path=os.path.join(instance_path, "growth_history.sqlite3"),
        )
        self.growth_history_service = GrowthHistoryService(
            self.growth_history_repository
        )
        self.cache = {}
        self.ai_response_cache = {}
        self.cache_lock = Lock()
        self.nexon_request_lock = Lock()
        self.last_nexon_request_at = 0.0
        self.nexon_request_count = 0
        self.request_limit_lock = Lock()
        self.ai_request_timestamps = {}
        self.ai_daily_usage = {}
        self.ai_global_daily_usage = {}
        self.admin_login_failures = {}


_fallback_runtime_state = None


def get_runtime_state():
    """현재 Flask 앱의 런타임 상태를 반환한다."""
    global _fallback_runtime_state
    if has_app_context():
        state = current_app.extensions.get("maple_growth_tracker")
        if state is not None:
            return state
    if _fallback_runtime_state is None:
        _fallback_runtime_state = RuntimeState()
    return _fallback_runtime_state


def get_growth_history_service():
    return get_runtime_state().growth_history_service


def get_gemini_client():
    return get_runtime_state().gemini_client


def configure_runtime(flask_app):
    """앱 전용 상태를 초기화하고 Flask extensions에 등록한다."""
    os.makedirs(flask_app.instance_path, exist_ok=True)
    state = RuntimeState(flask_app)
    flask_app.extensions["maple_growth_tracker"] = state
    with flask_app.app_context():
        initialize_log_db()
        initialize_snapshot_db()
    return state



def connect_log_db():
    state = get_runtime_state()
    if state.log_db_backend == "postgres":
        return psycopg.connect(
            state.growth_database_url,
            connect_timeout=3,
            sslmode="require",
            prepare_threshold=None,
            row_factory=dict_row,
        )

    connection = sqlite3.connect(state.log_db_path, timeout=5)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_log_db():
    state = get_runtime_state()

    if state.log_db_backend == "postgres":
        try:
            connection = connect_log_db()
            try:
                with connection:
                    connection.execute("""
                        CREATE TABLE IF NOT EXISTS action_logs (
                            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                            created_at TIMESTAMPTZ NOT NULL,
                            action TEXT NOT NULL,
                            character_name TEXT,
                            world_name TEXT,
                            comparison_name TEXT,
                            result TEXT NOT NULL,
                            path TEXT,
                            status_code INTEGER,
                            duration_ms INTEGER,
                            error_type TEXT
                        )
                    """)
                    for column, definition in (
                        ("path", "TEXT"),
                        ("status_code", "INTEGER"),
                        ("duration_ms", "INTEGER"),
                        ("error_type", "TEXT"),
                    ):
                        connection.execute(
                            f"ALTER TABLE action_logs ADD COLUMN IF NOT EXISTS {column} {definition}"
                        )
                    connection.execute(
                        "CREATE INDEX IF NOT EXISTS idx_action_logs_created_at "
                        "ON action_logs (created_at DESC)"
                    )
                    connection.execute("ALTER TABLE action_logs ENABLE ROW LEVEL SECURITY")
                    connection.execute(
                        "REVOKE ALL ON TABLE action_logs FROM PUBLIC, anon, authenticated"
                    )
            finally:
                connection.close()
            return
        except psycopg.Error:
            # 로그 저장소 장애가 앱 전체의 시작을 막지 않도록 로컬 저장소로 전환한다.
            print("영구 관리자 로그 저장소 초기화에 실패했습니다.")
            state.log_db_backend = "sqlite"
            state.log_storage_warning = (
                "Supabase 로그 저장소에 연결하지 못해 임시 SQLite를 사용 중입니다. "
                "이 환경의 로그는 재배포 후 유지되지 않을 수 있습니다."
            )

    connection = sqlite3.connect(state.log_db_path, timeout=5)
    try:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS action_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    character_name TEXT,
                    world_name TEXT,
                    comparison_name TEXT,
                    result TEXT NOT NULL,
                    path TEXT,
                    status_code INTEGER,
                    duration_ms INTEGER,
                    error_type TEXT
                )
            """)
            existing_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(action_logs)")
            }
            for column, definition in (
                ("path", "TEXT"),
                ("status_code", "INTEGER"),
                ("duration_ms", "INTEGER"),
                ("error_type", "TEXT"),
            ):
                if column not in existing_columns:
                    connection.execute(f"ALTER TABLE action_logs ADD COLUMN {column} {definition}")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_action_logs_created_at "
                "ON action_logs (created_at DESC)"
            )
    finally:
        connection.close()


def log_action(
    action,
    character_name=None,
    world_name=None,
    result="성공",
    comparison_name=None,
    path=None,
    status_code=None,
    duration_ms=None,
    error_type=None,
):
    """민감한 요청 본문은 저장하지 않고 운영에 필요한 행동 정보만 기록한다."""
    state = get_runtime_state()
    placeholder = "%s" if state.log_db_backend == "postgres" else "?"
    placeholders = ", ".join([placeholder] * 10)
    query = f"""
        INSERT INTO action_logs
            (created_at, action, character_name, world_name, comparison_name, result,
             path, status_code, duration_ms, error_type)
        VALUES ({placeholders})
    """
    try:
        connection = connect_log_db()
        try:
            with connection:
                connection.execute(
                    query,
                    (
                        datetime.now(KOREA_TIMEZONE).isoformat(timespec="seconds"),
                        action,
                        character_name,
                        world_name,
                        comparison_name,
                        result,
                        path,
                        status_code,
                        duration_ms,
                        error_type,
                    ),
                )
        finally:
            connection.close()
    except (sqlite3.Error, psycopg.Error):
        # DB 비밀번호, API 키, 요청 본문과 같은 상세 정보는 로그에 출력하지 않는다.
        print("관리자 로그 저장에 실패했습니다.")


def initialize_snapshot_db():
    state = get_runtime_state()
    state.snapshot_db_backend, state.snapshot_storage_warning = initialize_snapshot_db_for_path(
        state.snapshot_db_path, state.growth_database_url
    )
    return state.snapshot_db_backend


def get_ai_response_cache(prompt):
    """같은 프롬프트의 성공한 AI 결과를 일정 시간 재사용한다."""
    cache_key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    state = get_runtime_state()
    with state.cache_lock:
        cache = state.ai_response_cache
        item = cache.get(cache_key)
        if not item:
            return None

        now = time.time()
        if now - item["cached_at"] > AI_RESPONSE_CACHE_TTL:
            cache.pop(cache_key, None)
            return None

        item["used_at"] = now
        return item["analysis"]


def set_ai_response_cache(prompt, analysis):
    if not analysis:
        return

    now = time.time()
    cache_key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    state = get_runtime_state()
    with state.cache_lock:
        cache = state.ai_response_cache
        cache[cache_key] = {
            "analysis": analysis,
            "cached_at": now,
            "used_at": now,
        }

        while len(cache) > AI_RESPONSE_CACHE_MAX_ENTRIES:
            oldest_key = min(cache, key=lambda key: cache[key]["used_at"])
            cache.pop(oldest_key, None)


def get_cache(key):
    state = get_runtime_state()
    with state.cache_lock:
        cache = state.cache
        item = cache.get(key)
        if not item:
            return None
        now = time.time()
        if now - item["time"] > item["ttl"]:
            del cache[key]
            return None
        item["used_at"] = now
        return item["data"]


def set_cache(key, data, ttl):
    state = get_runtime_state()
    now = time.time()
    with state.cache_lock:
        cache = state.cache
        if len(cache) >= RUNTIME_CACHE_MAX_ENTRIES:
            for existing_key, item in list(cache.items()):
                if now - item["time"] > item["ttl"]:
                    cache.pop(existing_key, None)
        cache[key] = {
            "time": now,
            "used_at": now,
            "data": data,
            "ttl": ttl,
            "saved_at": datetime.now().astimezone().isoformat(timespec="seconds")
        }
        while len(cache) > RUNTIME_CACHE_MAX_ENTRIES:
            oldest_key = min(cache, key=lambda cache_key: cache[cache_key]["used_at"])
            cache.pop(oldest_key, None)


def get_cache_timestamp(key):
    state = get_runtime_state()
    with state.cache_lock:
        item = state.cache.get(key)
        if not item:
            return None
        if time.time() - item["time"] > item["ttl"]:
            state.cache.pop(key, None)
            return None
        return item.get("saved_at")


def save_api_snapshot(cache_key, data):
    state = get_runtime_state()
    return save_api_snapshot_for_path(
        state.snapshot_db_path, cache_key, data,
        state.growth_database_url, state.snapshot_db_backend
    )


def record_best_combat_power(ocid, combat_power, preset_numbers=None, observed_at=None, preset_signatures=None):
    """조회한 실제 전투력의 최고 관측값과 당시 프리셋 번호를 보존한다."""
    try:
        value = int(float(str(combat_power).replace(",", "").strip()))
    except (TypeError, ValueError):
        value = None
    key = f"combat-power-best:{ocid}"
    existing, _ = load_api_snapshot(key)
    existing = existing if isinstance(existing, dict) else {}
    if value is not None and value > 0:
        try:
            previous_value = int(existing.get("value") or 0)
        except (TypeError, ValueError):
            previous_value = 0
        if value > previous_value or not existing.get("value"):
            existing = {
                "value": value,
                "observedAt": observed_at or datetime.now(KOREA_TIMEZONE).isoformat(timespec="seconds"),
                "presetNumbers": preset_numbers,
                "presetSignatures": preset_signatures,
            }
            save_api_snapshot(key, existing)
    return existing or None


def load_api_snapshot(cache_key):
    state = get_runtime_state()
    return load_api_snapshot_for_path(
        state.snapshot_db_path, cache_key,
        state.growth_database_url, state.snapshot_db_backend
    )


def with_data_status(data, status, saved_at=None):
    result = dict(data)
    result["dataStatus"] = status
    result["dataAsOf"] = saved_at
    return result


def stale_snapshot_response(cache_key, error_message):
    snapshot, saved_at = load_api_snapshot(cache_key)
    if snapshot is not None:
        return jsonify(with_data_status(snapshot, "stale", saved_at)), 200
    return jsonify({"error": error_message}), 503


# 메인 화면
# 관리자 로그인 및 로그 조회

# 캐릭터 정보와 현재 랭킹 조회
def start_request_timer():
    request.environ["maple_request_started_at"] = time.perf_counter()


def record_user_action(response):
    """민감한 요청 본문은 저장하지 않고 사용자 행동과 응답 메타데이터를 기록한다."""
    endpoint = request.endpoint
    status_code = response.status_code
    status = "성공" if 200 <= status_code < 400 else "실패"
    started_at = request.environ.get("maple_request_started_at", time.perf_counter())
    duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
    error_type = None
    if status_code >= 500:
        error_type = "http_5xx"
    elif status_code >= 400:
        error_type = f"http_{status_code}"

    details = {
        "path": request.path,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "error_type": error_type,
    }

    if endpoint == "character.get_character":
        name = request.args.get("name", "").strip() or None
        data = response.get_json(silent=True) or {}
        log_action(
            "캐릭터 조회",
            character_name=data.get("characterName") or name,
            world_name=data.get("worldName"),
            result=status,
            **details,
        )
    elif endpoint == "history.get_history":
        name = request.args.get("name", "").strip() or None
        data = response.get_json(silent=True) or {}
        log_action(
            "성장 기록 조회",
            character_name=data.get("characterName") or name,
            world_name=data.get("worldName"),
            result=status,
            **details,
        )
    elif endpoint == "history.get_history_archive":
        log_action(
            "장기 기록 조회",
            result=status,
            **details,
        )
    elif endpoint == "ai.ai_analysis":
        name = request.args.get("name", "").strip() or None
        character = request.environ.get("maple_character_context", {})
        log_action(
            "AI 성장 분석",
            character_name=character.get("characterName") or name,
            world_name=character.get("worldName"),
            result=status,
            **details,
        )
    elif endpoint == "ai.ai_comparison":
        payload = request.get_json(silent=True) or {}
        primary = payload.get("primary", {}).get("character", {}) if isinstance(payload.get("primary"), dict) else {}
        comparison = payload.get("comparison", {}).get("character", {}) if isinstance(payload.get("comparison"), dict) else {}
        log_action(
            "캐릭터 비교",
            character_name=primary.get("characterName"),
            world_name=primary.get("worldName"),
            comparison_name=comparison.get("characterName"),
            result=status,
            **details,
        )

    if status_code >= 500:
        log_action("서비스 오류", result="실패", **details)
    return response


def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return error
    # 예외 메시지나 요청 헤더에는 민감정보가 포함될 수 있어 로그로 남기지 않는다.
    print("처리되지 않은 서버 오류가 발생했습니다.")
    return jsonify({"error": "서버에서 요청을 처리하지 못했습니다."}), 500



