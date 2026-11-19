"""최근 성장 기록의 Nexon API 수집 규칙."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests


def _now_utc_iso():
    """API 응답을 받은 시각을 UTC ISO-8601 형식으로 기록한다."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _positive_rank(value):
    """양의 정수인 랭킹 값만 유효한 순위로 취급한다."""
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        ranking = int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return ranking if ranking > 0 else None


def _get_cached_current_ranking(basic, target_date, today):
    """실제 집계일이 같은 종합 랭킹만 프로필 스냅샷에서 재사용한다."""
    if target_date != today or not isinstance(basic, dict):
        return None
    if basic.get("ranking_data_status") != "available":
        return None
    if basic.get("ranking_scope") != "overall":
        return None
    ranking_date = basic.get("ranking_date")
    if ranking_date != target_date.isoformat():
        return None
    ranking = _positive_rank(basic.get("ranking"))
    if ranking is None:
        return None
    return {
        "ranking": ranking,
        "ranking_scope": "overall",
        "ranking_source_date": ranking_date,
        "character_level": basic.get("character_level"),
        "character_exp": basic.get("character_exp"),
        "character_exp_rate": basic.get("character_exp_rate"),
        "_growthSource": basic.get("_growthSource") or "character/basic",
        "_growthObservedAt": basic.get("_growthObservedAt"),
    }


def _saved_record_without_unverified_ranking(date_string, saved):
    """기존 성장 데이터는 보존하고 실제 집계일을 확인하지 못한 순위는 숨긴다."""
    ranking = (
        _positive_rank(saved.get("ranking"))
        if (
            saved.get("rankingSourceDate") == date_string
            and saved.get("rankingScope") == "overall"
        )
        else None
    )
    return {
        "date": date_string,
        "ranking": ranking,
        "rankingScope": "overall" if ranking is not None else None,
        "rankingSourceDate": saved.get("rankingSourceDate"),
        "level": saved.get("level"),
        "experience": saved.get("experience"),
        "experienceRate": saved.get("experienceRate"),
        "experienceRateChecked": saved.get("experienceRateChecked", False),
        "growthSource": saved.get("growthSource"),
        "growthObservedAt": saved.get("growthObservedAt"),
        "recordStatus": saved.get("recordStatus"),
        "_fromStore": True,
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
            and saved.get("recordStatus") in ("unavailable", "not_ready")
        )
        or (
            saved is not None
            and saved.get("recordStatus") == "available"
            and (
                saved.get("rankingSourceDate") != date_string
                or (
                    saved.get("ranking") is not None
                    and saved.get("rankingScope") != "overall"
                )
                or not saved.get("experienceRateChecked", False)
                or not saved.get("growthSource")
                or not saved.get("growthObservedAt")
            )
        )
    )

    if saved and not should_check_api:
        return {
            "date": date_string,
            "ranking": saved.get("ranking"),
            "rankingScope": saved.get("rankingScope"),
            "rankingSourceDate": saved.get("rankingSourceDate"),
            "level": saved.get("level"),
            "experience": saved.get("experience"),
            "experienceRate": saved.get("experienceRate"),
            "experienceRateChecked": saved.get("experienceRateChecked", False),
            "growthSource": saved.get("growthSource"),
            "growthObservedAt": saved.get("growthObservedAt"),
            "recordStatus": saved.get("recordStatus"),
            "_fromStore": True,
        }

    ranking_data = _get_cached_current_ranking(basic, target_date, today)
    if ranking_data is not None:
        response = requests.Response()
        response.status_code = 200
        increment_metric("history.current_ranking_reused")
        growth_source = ranking_data.get("_growthSource") or "character/basic"
        growth_observed_at = ranking_data.get("_growthObservedAt") or _now_utc_iso()
    else:
        ranking_data, response = get_ranking_snapshot(
            target_date=date_string,
            world_name=None,
            ocid=ocid,
            world_type=get_world_type(world_name),
        )
        growth_source = "ranking/overall"
        growth_observed_at = _now_utc_iso()

    if ranking_data and response is not None and response.status_code == 200:
        growth_data = ranking_data
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
            if rate_data and rate_response and rate_response.status_code == 200:
                # 진행률이 별도 기본 정보 API에서 왔다면 레벨·EXP도 같은 응답에서 사용한다.
                # 서로 다른 시점의 API 응답을 하나의 날짜 스냅샷으로 섞지 않는다.
                if (
                    rate_data.get("character_level") is not None
                    and rate_data.get("character_exp") is not None
                ):
                    growth_data = rate_data
                    growth_source = "character/basic"
                    growth_observed_at = (
                        basic.get("_growthObservedAt") or _now_utc_iso()
                        if target_date == today
                        else _now_utc_iso()
                    )
                    experience_rate = rate_data.get("character_exp_rate")
                else:
                    # 기본 정보 응답이 성장 스냅샷 전체를 제공하지 못하면
                    # 해당 응답의 진행률만 랭킹 응답에 섞지 않는다.
                    experience_rate = None
            rate_checked = bool(
                rate_response is not None and rate_response.status_code == 200
            )
        ranking = _positive_rank(ranking_data.get("ranking"))
        return {
            "date": date_string,
            "ranking": ranking,
            "rankingScope": "overall" if ranking is not None else None,
            "rankingSourceDate": date_string,
            "level": growth_data.get("character_level"),
            "experience": growth_data.get("character_exp"),
            "experienceRate": experience_rate,
            "experienceRateChecked": rate_checked,
            "growthSource": growth_source,
            "growthObservedAt": growth_observed_at,
            "recordStatus": "available",
        }

    # 랭킹 API 오류는 데이터 없음과 구분한다. 기존 행은 보존하되
    # 집계일을 증명할 수 없는 순위는 이 응답에서 노출하지 않는다.
    if response is None or response.status_code != 200:
        # 오늘 캐릭터 기본 프로필은 현재 레벨·경험치의 유효한 원본이다.
        # 랭킹 API만 실패한 경우에도 프로필 성장 기록은 계속 저장한다.
        if target_date == today and isinstance(basic, dict):
            current_level = basic.get("character_level")
            current_experience = basic.get("character_exp")
            if current_level is not None and current_experience is not None:
                current_rate = basic.get("character_exp_rate")
                return {
                    "date": date_string,
                    "ranking": None,
                    "rankingScope": None,
                    "rankingSourceDate": None,
                    "level": current_level,
                    "experience": current_experience,
                    "experienceRate": current_rate,
                    "experienceRateChecked": current_rate is not None,
                    "growthSource": basic.get("_growthSource") or "character/basic",
                    "growthObservedAt": basic.get("_growthObservedAt") or _now_utc_iso(),
                    "recordStatus": "available",
                }
        if saved and saved.get("recordStatus") == "available":
            return _saved_record_without_unverified_ranking(date_string, saved)
        return {
            "date": date_string,
            "ranking": None,
            "rankingScope": None,
            "rankingSourceDate": None,
            "level": None,
            "experience": None,
            "experienceRate": None,
            "experienceRateChecked": False,
            "growthSource": None,
            "growthObservedAt": None,
            "recordStatus": "unavailable",
            "retryable": is_temporary_nexon_failure(response),
        }

    # 해당 날짜의 종합 랭킹 API가 정상적으로 빈 응답을 보낸 경우에만
    # 기본 정보 API로 레벨·경험치를 보충한다.
    try:
        basic_data, basic_response = get_basic_character_snapshot(
            ocid,
            target_date=date_string if target_date < today else None,
            historical=True,
        )
    except requests.RequestException:
        basic_data, basic_response = None, None

    if (
        basic_data
        and basic_response is not None
        and basic_response.status_code == 200
    ):
        level = basic_data.get("character_level")
        experience = basic_data.get("character_exp")
        if level is not None and experience is not None:
            return {
                "date": date_string,
                "ranking": None,
                "rankingScope": None,
                "rankingSourceDate": date_string,
                "level": level,
                "experience": experience,
                "experienceRate": basic_data.get("character_exp_rate"),
                "experienceRateChecked": True,
                "growthSource": "character/basic",
                "growthObservedAt": _now_utc_iso(),
                "recordStatus": "available",
            }

    # 랭킹 API가 정확한 날짜에 정상 응답했지만 순위가 없으면
    # 기존 레벨·경험치는 유지하고 미검증 순위만 제거해 저장한다.
    if saved and saved.get("recordStatus") == "available":
        return {
            "date": date_string,
            "ranking": None,
            "rankingScope": None,
            "rankingSourceDate": date_string,
            "level": saved.get("level"),
            "experience": saved.get("experience"),
            "experienceRate": saved.get("experienceRate"),
            "experienceRateChecked": saved.get("experienceRateChecked", False),
            "growthSource": saved.get("growthSource"),
            "growthObservedAt": saved.get("growthObservedAt"),
            "recordStatus": "available",
        }

    if basic_response is not None and basic_response.status_code == 200:
        return {
            "date": date_string,
            "ranking": None,
            "rankingScope": None,
            "rankingSourceDate": date_string,
            "level": None,
            "experience": None,
            "experienceRate": None,
            "experienceRateChecked": True,
            "growthSource": None,
            "growthObservedAt": None,
            "recordStatus": "not_ready",
        }

    return {
        "date": date_string,
        "ranking": None,
        "rankingScope": None,
        "rankingSourceDate": None,
        "level": None,
        "experience": None,
        "experienceRate": None,
        "experienceRateChecked": False,
        "growthSource": None,
        "growthObservedAt": None,
        "recordStatus": "unavailable",
        "retryable": is_temporary_nexon_failure(basic_response),
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
