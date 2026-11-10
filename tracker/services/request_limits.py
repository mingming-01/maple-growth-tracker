"""앱 인스턴스 단위의 AI 요청 한도와 관리자 로그인 잠금 정책."""
import hashlib
import ipaddress
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


def _api_rate_limit_identity_ready(remote_addr):
    """신뢰할 수 있는 실제 접속자 IP를 확인할 수 있을 때만 IP별 제한을 적용한다."""
    if not _setting("API_REQUEST_LIMITS_ENABLED", True):
        return False
    if (
        _setting("IS_PRODUCTION", False)
        and int(_setting("TRUSTED_PROXY_HOPS", 0) or 0) < 1
    ):
        # 프록시 주소를 모든 방문자의 IP로 오인해 전체 사용자를 함께 제한하지 않는다.
        return False
    try:
        address = ipaddress.ip_address(str(remote_addr or "").strip())
    except ValueError:
        return False
    return not (
        address.is_loopback
        or address.is_unspecified
        or address.is_multicast
    )


def _prune_timestamp_store(store, now, window_seconds, max_clients):
    """만료된 IP별 요청 기록을 정리하고 저장 항목 수도 제한한다."""
    for client_key, timestamps in list(store.items()):
        active = [
            stamp for stamp in timestamps
            if now - stamp < window_seconds
        ]
        if active:
            store[client_key] = active
        else:
            store.pop(client_key, None)

    while len(store) > max_clients:
        oldest_key = next(iter(store), None)
        if oldest_key is None:
            break
        store.pop(oldest_key, None)


def _consume_api_request_memory(
    state,
    key,
    now,
    window_seconds,
    request_limit,
    refresh_limit,
    force_refresh,
    max_clients,
    cleanup,
):
    with state.request_limit_lock:
        if cleanup:
            _prune_timestamp_store(
                state.api_request_timestamps,
                now,
                window_seconds,
                max_clients,
            )
            _prune_timestamp_store(
                state.api_refresh_timestamps,
                now,
                window_seconds,
                max_clients,
            )

        requests = state.api_request_timestamps.setdefault(key, [])
        requests[:] = [
            stamp for stamp in requests
            if now - stamp < window_seconds
        ]

        refreshes = state.api_refresh_timestamps.get(key, [])
        if force_refresh:
            refreshes = [
                stamp for stamp in refreshes
                if now - stamp < window_seconds
            ]

        if len(requests) >= request_limit:
            retry_after = max(
                1, math.ceil(window_seconds - (now - requests[0]))
            )
            return False, retry_after, "requests_per_minute"

        if force_refresh and len(refreshes) >= refresh_limit:
            retry_after = max(
                1, math.ceil(window_seconds - (now - refreshes[0]))
            )
            return False, retry_after, "refreshes_per_minute"

        requests.append(now)
        if force_refresh:
            state.api_refresh_timestamps[key] = refreshes
            state.api_refresh_timestamps[key].append(now)

    return True, 0, ""


def consume_api_request(remote_addr, force_refresh=False):
    """캐시 미스 요청과 강제 새로고침에 IP별 완화된 한도를 적용한다.

    PostgreSQL이 설정된 운영 환경에서는 앱 인스턴스가 공유하는 행 잠금으로
    워커 간 한도를 일관되게 적용한다. 로컬 SQLite는 프로세스 메모리를 사용한다.
    캐시 hit 경로에서는 이 함수를 호출하지 않는다.
    """
    if not _api_rate_limit_identity_ready(remote_addr):
        return True, 0, ""

    state = get_runtime_state()
    key = _client_key(remote_addr)
    now = time.monotonic()
    window_seconds = max(
        1, int(_setting("API_REQUEST_LIMIT_WINDOW_SECONDS", 60))
    )
    request_limit = max(
        1, int(_setting("API_REQUESTS_PER_MINUTE_PER_IP", 60))
    )
    refresh_limit = max(
        1, int(_setting("API_REFRESHES_PER_MINUTE_PER_IP", 12))
    )
    max_clients = max(
        100, int(_setting("API_RATE_LIMIT_MAX_CLIENTS", 10000))
    )

    with state.request_limit_lock:
        state.api_limit_cleanup_counter += 1
        cleanup = state.api_limit_cleanup_counter % 64 == 0
        shared_store_available = (
            now >= state.api_rate_limit_storage_unavailable_until
        )

    repository = getattr(state, "growth_history_repository", None)
    if (
        shared_store_available
        and getattr(repository, "uses_postgres", False)
        and callable(getattr(repository, "consume_api_rate_limit", None))
    ):
        try:
            return repository.consume_api_rate_limit(
                client_key=key,
                now=time.time(),
                window_seconds=window_seconds,
                request_limit=request_limit,
                refresh_limit=refresh_limit,
                force_refresh=force_refresh,
                max_clients=max_clients,
                cleanup=cleanup,
            )
        except Exception:
            with state.request_limit_lock:
                state.api_rate_limit_storage_unavailable_until = time.monotonic() + 30
                should_log = not state.api_rate_limit_storage_warning_logged
                state.api_rate_limit_storage_warning_logged = True
            if should_log and has_app_context():
                current_app.logger.warning(
                    "공유 API 요청 제한 저장소를 사용할 수 없어 프로세스 메모리 제한기로 전환했습니다."
                )

    return _consume_api_request_memory(
        state=state,
        key=key,
        now=now,
        window_seconds=window_seconds,
        request_limit=request_limit,
        refresh_limit=refresh_limit,
        force_refresh=force_refresh,
        max_clients=max_clients,
        cleanup=cleanup,
    )
