"""넥슨 Open API 요청과 응답 처리를 담당한다."""

from app import *
from threading import Lock

HISTORY_API_REQUEST_LOCK = Lock()
_last_history_api_request_at = 0.0


def request_nexon_api(endpoint, params, historical=False):
    """넥슨 API를 호출하며 과거 기록 수집 요청은 초당 호출 수를 제한한다."""
    global _last_history_api_request_at

    if historical:
        with HISTORY_API_REQUEST_LOCK:
            elapsed = time.monotonic() - _last_history_api_request_at
            if elapsed < HISTORY_API_MIN_INTERVAL:
                time.sleep(HISTORY_API_MIN_INTERVAL - elapsed)
            _last_history_api_request_at = time.monotonic()

    return requests.get(
        f"{BASE_URL}/{endpoint}",
        headers=HEADERS,
        params=params,
        timeout=NEXON_API_TIMEOUT
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


def get_ranking(target_date, world_name=None, ocid=None, character_class=None, historical=False):
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
