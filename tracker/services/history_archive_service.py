"""과거 성장 기록의 Nexon API 수집 규칙."""

import requests

from tracker.services.nexon_service import (
    get_basic_character_snapshot,
    get_ranking_snapshot,
    get_world_type,
)


def is_historical_data_missing(response):
    """정상 응답에서 해당 날짜의 기록이 비어 있는지 확인한다."""
    return response is not None and response.status_code == 200


def fetch_historical_record(ocid, world_name, target_date, today):
    """랭킹 또는 날짜별 캐릭터 정보에서 과거 일일 스냅샷을 만든다."""
    date_text = target_date.isoformat()
    try:
        ranking_data, ranking_response = get_ranking_snapshot(
            date_text, world_name=world_name, ocid=ocid,
            world_type=get_world_type(world_name), historical=True
        )
    except requests.RequestException:
        ranking_data, ranking_response = None, None

    if ranking_data:
        level = ranking_data.get("character_level")
        experience = ranking_data.get("character_exp")
        if level is not None and experience is not None:
            experience_rate = ranking_data.get("character_exp_rate")
            rate_checked = experience_rate is not None
            if experience_rate is None:
                try:
                    rate_data, rate_response = get_basic_character_snapshot(
                        ocid,
                        target_date=date_text if target_date < today else None,
                        historical=True
                    )
                except requests.RequestException:
                    rate_data, rate_response = None, None
                if rate_data:
                    experience_rate = rate_data.get("character_exp_rate")
                rate_checked = bool(
                    rate_response is not None and rate_response.status_code == 200
                )
            return {
                "date": date_text,
                "ranking": ranking_data.get("ranking"),
                "level": level,
                "experience": experience,
                "experienceRate": experience_rate,
                "experienceRateChecked": rate_checked,
                "recordStatus": "available"
            }

    try:
        # 기본 정보 API는 오늘 날짜를 date로 받지 않으므로 오늘은 최신 응답을 사용한다.
        basic_data, basic_response = get_basic_character_snapshot(
            ocid,
            target_date=date_text if target_date < today else None,
            historical=True
        )
    except requests.RequestException:
        basic_data, basic_response = None, None

    if basic_data:
        level = basic_data.get("character_level")
        experience = basic_data.get("character_exp")
        if level is not None and experience is not None:
            return {
                "date": date_text,
                "ranking": ranking_data.get("ranking") if ranking_data else None,
                "level": level,
                "experience": experience,
                "experienceRate": basic_data.get("character_exp_rate"),
                "experienceRateChecked": bool(
                    basic_response is not None and basic_response.status_code == 200
                ),
                "recordStatus": "available"
            }

    # 명확한 데이터 없음 응답만 저장해 다음 조회 때 같은 날짜를 반복 요청하지 않는다.
    if (
        is_historical_data_missing(ranking_response)
        and is_historical_data_missing(basic_response)
    ):
        return {"date": date_text, "recordStatus": "not_ready"}

    # API 오류는 미수집 상태로 남겨 다음 사용자의 요청 때 다시 확인할 수 있게 한다.
    return None
