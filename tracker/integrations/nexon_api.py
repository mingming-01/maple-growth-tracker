"""넥슨 Open API 요청과 응답 처리를 담당한다."""
import hashlib
import json
import time
from concurrent.futures import Future
from threading import Lock

import requests
from flask import current_app, has_app_context

from tracker.config import Config
from tracker.repositories.growth_history_store import GrowthHistoryStore
from tracker.integrations.http_client import request_with_retries
from tracker.services.performance_metrics import increment_metric, observe_metric

BASE_URL = "https://open.api.nexon.com/maplestory/v1"
DEFAULT_NEXON_API_MIN_INTERVAL = 0.22
_fallback_rate_limit_lock = Lock()
_fallback_last_request_at = 0.0
_shared_repository = None
_shared_repository_lock = Lock()
_inflight_requests = {}
_inflight_requests_lock = Lock()


def _setting(name, default=None):
    if has_app_context():
        return current_app.config.get(name, default)
    return getattr(Config, name, default)


def _throttle_nexon_request():
    """모든 Nexon API 요청 시작 간격을 앱 단위로 제한한다."""
    global _fallback_last_request_at

    if has_app_context():
        state = current_app.extensions.get("maple_growth_tracker")
    else:
        state = None

    # Flask 요청 스레드와 ThreadPoolExecutor 작업자가 같은 프로세스 제한기를 공유한다.
    lock = _fallback_rate_limit_lock
    try:
        min_interval = max(0.0, float(_setting("NEXON_API_MIN_INTERVAL", DEFAULT_NEXON_API_MIN_INTERVAL)))
    except (TypeError, ValueError):
        min_interval = DEFAULT_NEXON_API_MIN_INTERVAL

    repository = None
    if state:
        repository = getattr(state, "growth_history_repository", None)
    elif str(_setting("GROWTH_DATABASE_URL", "")).startswith(("postgres://", "postgresql://")):
        global _shared_repository
        with _shared_repository_lock:
            if _shared_repository is None:
                _shared_repository = GrowthHistoryStore(
                    database_url=_setting("GROWTH_DATABASE_URL", "")
                )
            repository = _shared_repository

    if (
        getattr(repository, "uses_postgres", False)
        and callable(getattr(repository, "reserve_nexon_request_slot", None))
    ):
        try:
            wait_seconds = repository.reserve_nexon_request_slot(
                now=time.time(),
                min_interval=min_interval,
            )
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            if state:
                state.last_nexon_request_at = time.monotonic()
                state.nexon_request_count += 1
            return
        except Exception:
            if has_app_context():
                current_app.logger.warning(
                    "공유 Nexon 요청 간격 저장소를 사용할 수 없어 프로세스 제한기로 전환했습니다."
                )

    while True:
        with lock:
            now = time.monotonic()
            elapsed = now - _fallback_last_request_at
            if elapsed >= min_interval:
                requested_at = now
                _fallback_last_request_at = requested_at
                if state:
                    state.last_nexon_request_at = requested_at
                    state.nexon_request_count += 1
                break
            wait_seconds = min_interval - elapsed

        # 락을 해제한 뒤 대기하고, 다시 진입해 다른 스레드가 먼저 예약했는지 확인한다.
        if wait_seconds > 0:
            time.sleep(wait_seconds)


def request_nexon_api(endpoint, params, historical=False, timeout_override=None, max_attempts_override=None):
    """넥슨 API 요청에 공통 호출 간격 제한·재시도와 동일 진행 요청 병합을 적용한다."""
    api_key = _setting("NEXON_API_KEY", "")
    headers = {"x-nxopen-api-key": api_key} if api_key else {}
    timeout = timeout_override or (
        float(_setting("NEXON_API_CONNECT_TIMEOUT", 3.05)),
        float(_setting("NEXON_API_READ_TIMEOUT", 10)),
    )
    retries = _setting("NEXON_API_RETRIES", 2)
    backoff = _setting("NEXON_API_RETRY_BACKOFF", 0.35)
    try:
        retries = int(retries)
    except (TypeError, ValueError):
        retries = 2
    try:
        backoff = float(backoff)
    except (TypeError, ValueError):
        backoff = 0.35

    max_attempts = retries + 1
    if max_attempts_override is not None:
        try:
            max_attempts = max(1, int(max_attempts_override))
        except (TypeError, ValueError):
            max_attempts = retries + 1
    max_retry_after_wait = max(
        0.0,
        float(_setting("EXTERNAL_API_MAX_RETRY_AFTER_WAIT_SECONDS", 5.0)),
    )

    # API 키 자체는 메모리의 병합 키에 보관하지 않는다. 요청 결과를 공유할 수 있는
    # 동일 인증·파라미터·timeout·재시도 설정만 같은 진행 요청으로 취급한다.
    request_key = (
        str(endpoint),
        json.dumps(params or {}, ensure_ascii=False, sort_keys=True, default=str),
        hashlib.sha256(str(api_key).encode("utf-8")).hexdigest(),
        repr(timeout),
        bool(historical),
        max_attempts,
        max(0.0, backoff),
        max_retry_after_wait,
    )
    started_at = time.perf_counter()
    increment_metric("nexon.logical_requests", endpoint=endpoint)

    with _inflight_requests_lock:
        future = _inflight_requests.get(request_key)
        is_leader = future is None
        if is_leader:
            future = Future()
            _inflight_requests[request_key] = future

    if not is_leader:
        increment_metric("nexon.coalesced_requests", endpoint=endpoint)
        try:
            response = future.result()
        except BaseException:
            observe_metric(
                "nexon.logical_request_ms",
                (time.perf_counter() - started_at) * 1000,
                endpoint=endpoint,
            )
            raise
        observe_metric(
            "nexon.logical_request_ms",
            (time.perf_counter() - started_at) * 1000,
            endpoint=endpoint,
        )
        return response

    def on_attempt(attempt):
        increment_metric("nexon.attempts", endpoint=endpoint)
        if attempt > 1:
            increment_metric("nexon.retries", endpoint=endpoint)

    def on_response(attempt, response, elapsed_ms):
        status_code = getattr(response, "status_code", "unknown")
        increment_metric("nexon.responses", endpoint=endpoint, status=status_code)
        observe_metric("nexon.attempt_ms", elapsed_ms, endpoint=endpoint)

    def on_error(attempt, error, elapsed_ms):
        increment_metric("nexon.errors", endpoint=endpoint, error=type(error).__name__)
        observe_metric("nexon.attempt_ms", elapsed_ms, endpoint=endpoint)

    try:
        response = request_with_retries(
            "get",
            f"{BASE_URL}/{endpoint}",
            headers=headers,
            params=params,
            timeout=timeout,
            max_attempts=max_attempts,
            backoff_factor=max(0.0, backoff),
            max_retry_after_wait=max_retry_after_wait,
            before_attempt=_throttle_nexon_request,
            on_attempt=on_attempt,
            on_response=on_response,
            on_error=on_error,
        )
    except BaseException as error:
        future.set_exception(error)
        observe_metric(
            "nexon.logical_request_ms",
            (time.perf_counter() - started_at) * 1000,
            endpoint=endpoint,
        )
        raise
    else:
        future.set_result(response)
        observe_metric(
            "nexon.logical_request_ms",
            (time.perf_counter() - started_at) * 1000,
            endpoint=endpoint,
        )
        return response
    finally:
        with _inflight_requests_lock:
            if _inflight_requests.get(request_key) is future:
                _inflight_requests.pop(request_key, None)


def get_ocid(character_name, timeout_override=None, max_attempts_override=None):
    options = {}
    if timeout_override is not None:
        options["timeout_override"] = timeout_override
    if max_attempts_override is not None:
        options["max_attempts_override"] = max_attempts_override
    response = request_nexon_api("id", {"character_name": character_name}, **options)
    if response.status_code != 200:
        return None, response
    return response.json()["ocid"], response


def get_basic_character(
    ocid, target_date=None, historical=False,
    timeout_override=None, max_attempts_override=None,
):
    """캐릭터 기본 정보를 조회하며, 날짜를 지정하면 해당 날짜의 스냅샷을 요청한다."""
    params = {"ocid": ocid}
    if target_date:
        params["date"] = target_date
    options = {}
    if timeout_override is not None:
        options["timeout_override"] = timeout_override
    if max_attempts_override is not None:
        options["max_attempts_override"] = max_attempts_override
    response = request_nexon_api("character/basic", params, historical, **options)
    if response.status_code != 200:
        return None, response
    return response.json(), response


def get_ranking_page(
    target_date,
    world_name=None,
    character_class=None,
    world_type=0,
    page=1,
    historical=False,
):
    """필터링된 랭킹 페이지를 조회한다. OCID 단건 필터는 사용하지 않는다."""
    params = {
        "date": target_date,
        "world_type": int(world_type),
        "page": max(1, int(page)),
    }
    if world_name:
        params["world_name"] = world_name
    if character_class:
        params["class"] = character_class

    response = request_nexon_api("ranking/overall", params, historical)
    if response.status_code != 200:
        return [], response
    ranking_list = response.json().get("ranking", [])
    return ranking_list if isinstance(ranking_list, list) else [], response


def get_ranking(
    target_date,
    world_name=None,
    ocid=None,
    character_class=None,
    world_type=0,
    historical=False,
):
    """OCID로 특정 캐릭터의 일반·월드 랭킹을 조회한다."""
    params = {"date": target_date, "world_type": int(world_type), "page": 1}
    if world_name:
        params["world_name"] = world_name
    if character_class:
        params["class"] = character_class
    if ocid:
        params["ocid"] = ocid

    response = request_nexon_api("ranking/overall", params, historical)
    if response.status_code != 200:
        return None, response
    ranking_list = response.json().get("ranking", [])
    if not ranking_list:
        return None, response
    return ranking_list[0], response
