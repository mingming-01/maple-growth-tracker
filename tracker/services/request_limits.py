"""앱 인스턴스 단위의 AI 요청 한도와 관리자 로그인 잠금 정책."""
import hashlib
import math
import time
from datetime import datetime, time as datetime_time, timedelta
from flask import current_app, has_app_context
from tracker.runtime import KOREA_TIMEZONE, get_runtime_state


def _setting(name, default):
    return current_app.config.get(name, default) if has_app_context() else default


def _client_key(remote_addr):
    return hashlib.sha256(str(remote_addr or "unknown").encode("utf-8")).hexdigest()


def _seconds_until_kst_midnight():
    now = datetime.now(KOREA_TIMEZONE)
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime_time.min, tzinfo=KOREA_TIMEZONE)
    return max(1, math.ceil((midnight - now).total_seconds()))


def consume_ai_request(remote_addr):
    """분당·IP별 일일·인스턴스 전체 일일 요청 한도를 원자적으로 적용한다."""
    state = get_runtime_state()
    key = _client_key(remote_addr)
    now = time.monotonic()
    today = datetime.now(KOREA_TIMEZONE).date().isoformat()
    per_minute_limit = max(1, int(_setting("AI_MAX_REQUESTS_PER_MINUTE", 5)))
    per_ip_daily_limit = max(1, int(_setting("AI_MAX_REQUESTS_PER_DAY_PER_IP", 20)))
    global_daily_limit = max(1, int(_setting("AI_MAX_REQUESTS_PER_DAY_GLOBAL", 100)))

    with state.request_limit_lock:
        timestamps = state.ai_request_timestamps.setdefault(key, [])
        timestamps[:] = [stamp for stamp in timestamps if now - stamp < 60]
        if len(timestamps) >= per_minute_limit:
            return False, max(1, math.ceil(60 - (now - timestamps[0]))), "minute"

        daily_key = f"{today}:{key}"
        if state.ai_daily_usage.get(daily_key, 0) >= per_ip_daily_limit:
            return False, _seconds_until_kst_midnight(), "client_daily"
        if state.ai_global_daily_usage.get(today, 0) >= global_daily_limit:
            return False, _seconds_until_kst_midnight(), "global_daily"

        timestamps.append(now)
        state.ai_daily_usage[daily_key] = state.ai_daily_usage.get(daily_key, 0) + 1
        state.ai_global_daily_usage[today] = state.ai_global_daily_usage.get(today, 0) + 1
        for stale_key in list(state.ai_daily_usage):
            if not stale_key.startswith(f"{today}:"):
                state.ai_daily_usage.pop(stale_key, None)
        for stale_day in list(state.ai_global_daily_usage):
            if stale_day != today:
                state.ai_global_daily_usage.pop(stale_day, None)
    return True, 0, ""


def admin_login_lockout_remaining(remote_addr):
    state = get_runtime_state()
    key = _client_key(remote_addr)
    now = time.monotonic()
    window = max(60, int(_setting("ADMIN_LOGIN_WINDOW_SECONDS", 900)))
    with state.request_limit_lock:
        entry = state.admin_login_failures.get(key)
        if not entry:
            return 0
        if entry.get("locked_until", 0) > now:
            return max(1, math.ceil(entry["locked_until"] - now))
        if now - entry.get("window_started", now) >= window:
            state.admin_login_failures.pop(key, None)
        return 0


def record_admin_login_failure(remote_addr):
    """로그인 실패를 기록하고 임계 횟수 도달 시 일정 시간 잠근다."""
    state = get_runtime_state()
    key = _client_key(remote_addr)
    now = time.monotonic()
    max_attempts = max(1, int(_setting("ADMIN_LOGIN_MAX_ATTEMPTS", 5)))
    window = max(60, int(_setting("ADMIN_LOGIN_WINDOW_SECONDS", 900)))
    lockout = max(60, int(_setting("ADMIN_LOGIN_LOCKOUT_SECONDS", 900)))
    with state.request_limit_lock:
        entry = state.admin_login_failures.get(key)
        if not entry or now - entry.get("window_started", now) >= window:
            entry = {"window_started": now, "attempts": 0, "locked_until": 0}
            state.admin_login_failures[key] = entry
        if entry.get("locked_until", 0) > now:
            return max(1, math.ceil(entry["locked_until"] - now))
        entry["attempts"] += 1
        if entry["attempts"] >= max_attempts:
            entry["locked_until"] = now + lockout
            return lockout
        return 0


def clear_admin_login_failures(remote_addr):
    state = get_runtime_state()
    key = _client_key(remote_addr)
    with state.request_limit_lock:
        state.admin_login_failures.pop(key, None)
