"""과거 성장 기록의 Nexon API 수집 규칙."""

from datetime import datetime, timezone

import requests

from tracker.services.nexon_service import (
    get_basic_character_snapshot,
    get_ranking_snapshot,
    get_world_type,
)


def _now_utc_iso():
    """API 응답 수신 시각을 UTC ISO-8601 형식으로 반환한다."""
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


def is_historical_data_missing(response):
    """정상 응답에서 해당 날짜의 기록이 비어 있는지 확인한다."""
    return response is not None and response.status_code == 200


def fetch_historical_record(
    ocid, world_name, target_date, today, saved_record=None
):
    """요청 날짜의 종합 랭킹을 검증하고 성장 데이터는 안전하게 보존한다."""
    date_text = target_date.isoformat()
    try:
        ranking_data, ranking_response = get_ranking_snapshot(
            date_text,
            world_name=None,
            ocid=ocid,
            world_type=get_world_type(world_name),
            historical=True,
        )
    except requests.RequestException:
        ranking_data, ranking_response = None, None

    # 랭킹 API가 정확한 날짜에 정상 응답하지 않았다면 저장하지 않는다.
    # 기본 정보 API만 성공했다고 기존 순위나 기록을 덮어쓰지 않는다.
    if not is_historical_data_missing(ranking_response):
        return None

    if ranking_data:
        level = ranking_data.get("character_level")
        experience = ranking_data.get("character_exp")
        if level is None or experience is None:
            return None

        growth_data = ranking_data
        growth_source = "ranking/overall"
        growth_observed_at = _now_utc_iso()
        experience_rate = ranking_data.get("character_exp_rate")
        rate_checked = experience_rate is not None
        if experience_rate is None:
            try:
                rate_data, rate_response = get_basic_character_snapshot(
                    ocid,
                    target_date=date_text if target_date < today else None,
                    historical=True,
                )
            except requests.RequestException:
                rate_data, rate_response = None, None
            if rate_data and rate_response and rate_response.status_code == 200:
                # 진행률을 기본 정보 API에서 보충할 때는 레벨·EXP도 같은 응답으로 통일한다.
                # 두 API의 서로 다른 스냅샷을 한 날짜의 성장 데이터로 혼합하지 않는다.
                if (
                    rate_data.get("character_level") is not None
                    and rate_data.get("character_exp") is not None
                ):
                    growth_data = rate_data
                    growth_source = "character/basic"
                    growth_observed_at = _now_utc_iso()
                    experience_rate = rate_data.get("character_exp_rate")
                else:
                    experience_rate = None
            rate_checked = bool(
                rate_response is not None and rate_response.status_code == 200
            )

        ranking = _positive_rank(ranking_data.get("ranking"))
        return {
            "date": date_text,
            "ranking": ranking,
            "rankingScope": "overall" if ranking is not None else None,
            "rankingSourceDate": date_text,
            "level": growth_data.get("character_level"),
            "experience": growth_data.get("character_exp"),
            "experienceRate": experience_rate,
            "experienceRateChecked": rate_checked,
            "growthSource": growth_source,
            "growthObservedAt": growth_observed_at,
            "recordStatus": "available",
        }

    # 랭킹 API가 정확한 날짜에 정상 응답했지만 종합 순위가 없다.
    # 이때만 기본 정보 API를 보조 조회해 경험치와 레벨을 보충한다.
    try:
        basic_data, basic_response = get_basic_character_snapshot(
            ocid,
            target_date=date_text if target_date < today else None,
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
                "date": date_text,
                "ranking": None,
                "rankingScope": None,
                "rankingSourceDate": date_text,
                "level": level,
                "experience": experience,
                "experienceRate": basic_data.get("character_exp_rate"),
                "experienceRateChecked": True,
                "growthSource": "character/basic",
                "growthObservedAt": _now_utc_iso(),
                "recordStatus": "available",
            }

    # 순위 API의 날짜별 빈 응답은 확인됐으므로 기존 레벨/경험치는 보존하고
    # 검증되지 않은 순위만 제거한다. 기본 정보 API 장애로 성장 데이터까지 지우지 않는다.
    if saved_record and saved_record.get("recordStatus") == "available":
        return {
            "date": date_text,
            "ranking": None,
            "rankingScope": None,
            "rankingSourceDate": date_text,
            "level": saved_record.get("level"),
            "experience": saved_record.get("experience"),
            "experienceRate": saved_record.get("experienceRate"),
            "experienceRateChecked": saved_record.get(
                "experienceRateChecked", False
            ),
            "growthSource": saved_record.get("growthSource"),
            "growthObservedAt": saved_record.get("growthObservedAt"),
            "recordStatus": "available",
        }

    # 랭킹과 기본 정보 API가 모두 정상적으로 해당 날짜의 기록이 없다고 답한 경우만
    # not_ready를 남겨 반복 수집을 줄인다.
    if is_historical_data_missing(basic_response):
        return {"date": date_text, "recordStatus": "not_ready"}

    # 일시 오류 또는 불완전한 응답은 DB에 반영하지 않아 다음 요청에서 재시도한다.
    return None
