"""최근 성장 기록의 Nexon API 수집 규칙."""

from concurrent.futures import ThreadPoolExecutor

import requests


def _get_cached_current_ranking(basic, target_date, today):
    """캐릭터 조회 스냅샷에서 오늘 종합 랭킹을 안전하게 추출한다."""
    if target_date != today or not isinstance(basic, dict):
        return None
    if basic.get("ranking_data_status") != "available":
        return None
    ranking = basic.get("ranking")
    if ranking is None:
        return None
    return {
        "ranking": ranking,
        "character_level": basic.get("character_level"),
        "character_exp": basic.get("character_exp"),
        "character_exp_rate": basic.get("character_exp_rate"),
    }


def _fetch_recent_record(
    target_date,
    *,
    basic,
    ocid,
    world_name,
    stored_recent,
    today,
    get_ranking_snapshot,
    get_basic_character_snapshot,
    get_world_type,
    is_temporary_nexon_failure,
    increment_metric,
):
    """하루치 기록을 저장소 우선·랭킹 API 우선 순서로 수집한다."""
    date_string = target_date.strftime("%Y-%m-%d")
    saved = stored_recent.get(date_string)
    should_check_api = (
        target_date == today
        or (
            saved is not None
            and saved.get("recordStatus") == "unavailable"
        )
        or (
            saved is not None
            and saved.get("recordStatus") == "available"
            and (
                not saved.get("experienceRateChecked", False)
                or saved.get("experienceRate") is None
            )
        )
    )

    if saved and not should_check_api:
        return {
            "date": date_string,
            "ranking": saved.get("ranking"),
            "level": saved.get("level"),
            "experience": saved.get("experience"),
            "experienceRate": saved.get("experienceRate"),
            "experienceRateChecked": saved.get("experienceRateChecked", False),
            "recordStatus": saved.get("recordStatus"),
            "_fromStore": True,
        }

    ranking_data = _get_cached_current_ranking(basic, target_date, today)
    if ranking_data is not None:
        response = requests.Response()
        response.status_code = 200
        increment_metric("history.current_ranking_reused")
    else:
        ranking_data, response = get_ranking_snapshot(
            target_date=date_string,
            world_name=world_name,
            ocid=ocid,
            world_type=get_world_type(world_name),
        )

    if ranking_data:
        experience_rate = ranking_data.get("character_exp_rate")
        rate_checked = experience_rate is not None
        if experience_rate is None:
            if target_date == today:
                rate_data, rate_response = basic, response
            else:
                try:
                    rate_data, rate_response = get_basic_character_snapshot(
                        ocid, target_date=date_string, historical=True
                    )
                except requests.RequestException:
                    rate_data, rate_response = None, None
            if rate_data:
                experience_rate = rate_data.get("character_exp_rate")
            rate_checked = bool(
                rate_response is not None and rate_response.status_code == 200
            )
        return {
            "date": date_string,
            "ranking": ranking_data.get("ranking"),
            "level": ranking_data.get("character_level"),
            "experience": ranking_data.get("character_exp"),
            "experienceRate": experience_rate,
            "experienceRateChecked": rate_checked,
            "recordStatus": "available",
        }

    # 429/5xx 등 일시적 랭킹 API 오류에는 기본 정보 API를 연쇄 호출하지 않는다.
    if is_temporary_nexon_failure(response):
        if saved and saved.get("recordStatus") == "available":
            return {
                "date": date_string,
                "ranking": saved.get("ranking"),
                "level": saved.get("level"),
                "experience": saved.get("experience"),
                "experienceRate": saved.get("experienceRate"),
                "experienceRateChecked": saved.get("experienceRateChecked", False),
                "recordStatus": "available",
                "_fromStore": True,
            }
        return {
            "date": date_string,
            "ranking": None,
            "level": None,
            "experience": None,
            "experienceRate": None,
            "experienceRateChecked": False,
            "recordStatus": "unavailable",
            "retryable": True,
        }

    # 정상 응답으로 랭킹 항목이 없을 때만 기본 정보 API를 보조 조회한다.
    try:
        basic_data, basic_response = get_basic_character_snapshot(
            ocid,
            target_date=date_string if target_date < today else None,
            historical=True,
        )
    except requests.RequestException:
        basic_data, basic_response = None, None

    if basic_data:
        level = basic_data.get("character_level")
        experience = basic_data.get("character_exp")
        if level is not None and experience is not None:
            return {
                "date": date_string,
                "ranking": None,
                "level": level,
                "experience": experience,
                "experienceRate": basic_data.get("character_exp_rate"),
                "experienceRateChecked": bool(
                    basic_response is not None and basic_response.status_code == 200
                ),
                "recordStatus": "available",
            }

    # 빈 응답으로 기존 정상 스냅샷을 덮어쓰지 않는다.
    if saved and saved.get("recordStatus") == "available":
        return {
            "date": date_string,
            "ranking": saved.get("ranking"),
            "level": saved.get("level"),
            "experience": saved.get("experience"),
            "experienceRate": saved.get("experienceRate"),
            "experienceRateChecked": saved.get("experienceRateChecked", False),
            "recordStatus": "available",
            "_fromStore": True,
        }

    if (
        response is not None and response.status_code == 200
        and basic_response is not None and basic_response.status_code == 200
    ):
        return {
            "date": date_string,
            "ranking": None,
            "level": None,
            "experience": None,
            "experienceRate": None,
            "experienceRateChecked": True,
            "recordStatus": "not_ready",
        }

    retryable = (
        is_temporary_nexon_failure(response)
        or is_temporary_nexon_failure(basic_response)
    )
    return {
        "date": date_string,
        "ranking": None,
        "level": None,
        "experience": None,
        "experienceRate": None,
        "experienceRateChecked": False,
        "recordStatus": "unavailable",
        "retryable": retryable,
    }


def fetch_recent_history(
    target_dates,
    *,
    basic,
    ocid,
    world_name,
    stored_recent,
    today,
    get_ranking_snapshot,
    get_basic_character_snapshot,
    get_world_type,
    is_temporary_nexon_failure,
    increment_metric,
    max_workers=3,
):
    """최근 날짜들을 제한된 병렬도로 조회하고 화면 표시 순서로 반환한다."""
    def fetch_one(target_date):
        return _fetch_recent_record(
            target_date,
            basic=basic,
            ocid=ocid,
            world_name=world_name,
            stored_recent=stored_recent,
            today=today,
            get_ranking_snapshot=get_ranking_snapshot,
            get_basic_character_snapshot=get_basic_character_snapshot,
            get_world_type=get_world_type,
            is_temporary_nexon_failure=is_temporary_nexon_failure,
            increment_metric=increment_metric,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        records = list(executor.map(fetch_one, target_dates))
    records.reverse()
    return records
