"""넥슨 Open API 요청과 응답 처리를 담당한다."""
import time
from threading import Lock

from flask import current_app, has_app_context

from tracker.config import Config
from tracker.integrations.http_client import request_with_retries

BASE_URL = "https://open.api.nexon.com/maplestory/v1"
HISTORY_API_MIN_INTERVAL = 0.22
_fallback_rate_limit_lock = Lock()
_fallback_last_request_at = 0.0


def _setting(name, default=None):
    if has_app_context():
        return current_app.config.get(name, default)
    return getattr(Config, name, default)


def _throttle_historical_request():
    """과거 데이터 호출 간격을 현재 앱 단위로 제한한다."""
    global _fallback_last_request_at

    if has_app_context():
        state = current_app.extensions.get("maple_growth_tracker")
    else:
        state = None

    lock = state.nexon_request_lock if state else _fallback_rate_limit_lock
    with lock:
        previous = state.last_nexon_request_at if state else _fallback_last_request_at
        elapsed = time.monotonic() - previous
        if elapsed < HISTORY_API_MIN_INTERVAL:
            time.sleep(HISTORY_API_MIN_INTERVAL - elapsed)
        requested_at = time.monotonic()
        if state:
            state.last_nexon_request_at = requested_at
        else:
            _fallback_last_request_at = requested_at


def request_nexon_api(endpoint, params, historical=False):
    """넥슨 API 요청에 제한 재시도와 과거 기록 호출 간격 제한을 적용한다."""
    api_key = _setting("NEXON_API_KEY", "")
    headers = {"x-nxopen-api-key": api_key} if api_key else {}
    timeout = (
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

    return request_with_retries(
        "get",
        f"{BASE_URL}/{endpoint}",
        headers=headers,
        params=params,
        timeout=timeout,
        max_attempts=retries + 1,
        backoff_factor=max(0.0, backoff),
        before_attempt=_throttle_historical_request if historical else None,
    )


def get_ocid(character_name):
    response = request_nexon_api("id", {"character_name": character_name})
    if response.status_code != 200:
        return None, response
    return response.json()["ocid"], response


def get_basic_character(ocid, target_date=None, historical=False):
    """캐릭터 기본 정보를 조회하며, 날짜를 지정하면 해당 날짜의 스냅샷을 요청한다."""
    params = {"ocid": ocid}
    if target_date:
        params["date"] = target_date
    response = request_nexon_api("character/basic", params, historical)
    if response.status_code != 200:
        return None, response
    return response.json(), response


def get_ranking(
    target_date,
    world_name=None,
    ocid=None,
    character_class=None,
    historical=False,
):
    params = {"date": target_date, "world_type": 0, "page": 1}
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
