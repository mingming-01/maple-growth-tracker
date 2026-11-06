"""Nexon Open API 응답을 애플리케이션 기능에 맞게 조합하는 서비스."""
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import current_app, has_app_context

from tracker.integrations.nexon_api import (
    get_basic_character,
    get_ocid,
    get_ranking,
    request_nexon_api,
)


def resolve_character(character_name):
    """캐릭터명으로 OCID와 기본 정보를 순서대로 확인한다."""
    ocid, response = get_ocid(character_name)
    if not ocid:
        return None, None, response

    basic, response = get_basic_character(ocid)
    return ocid, basic, response


def get_basic_character_snapshot(ocid, target_date=None, historical=False):
    """캐릭터 기본 정보 스냅샷을 조회한다."""
    return get_basic_character(
        ocid, target_date=target_date, historical=historical
    )


def get_ranking_snapshot(
    target_date,
    world_name=None,
    ocid=None,
    character_class=None,
    historical=False,
):
    """캐릭터 랭킹 스냅샷을 조회한다."""
    return get_ranking(
        target_date=target_date,
        world_name=world_name,
        ocid=ocid,
        character_class=character_class,
        historical=historical,
    )


def _jobs_path():
    if has_app_context():
        return Path(current_app.root_path) / "static" / "jobs.json"
    return Path(__file__).resolve().parents[2] / "static" / "jobs.json"


def get_api_class(character_class):
    """Nexon API가 사용하는 직업 분류 이름을 매핑한다."""
    try:
        with _jobs_path().open("r", encoding="utf-8") as file:
            jobs_data = json.load(file)
    except (OSError, ValueError):
        print("jobs.json 로드에 실패했습니다.")
        return None
    return jobs_data.get(character_class)


def get_character_rankings(target_date, world_name, character_class, ocid):
    """전체·월드·직업·직업 월드 랭킹을 조회한다.

    랭킹 데이터는 당일 집계가 아직 게시되지 않을 수 있으므로,
    당일 결과가 완전히 비어 있는 경우에만 직전 2일을 순서대로 확인한다.
    인증·호출 제한 등 날짜와 무관한 오류는 과거 날짜 재시도로 숨기지 않는다.
    """
    from datetime import datetime, timedelta

    api_class = get_api_class(character_class)
    try:
        requested_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        requested_date = datetime.now(ZoneInfo("Asia/Seoul")).date()

    def fetch_for_date(date_value):
        date_text = date_value.isoformat()

        def fetch_overall():
            return get_ranking_snapshot(target_date=date_text, ocid=ocid)

        def fetch_world():
            return get_ranking_snapshot(
                target_date=date_text, world_name=world_name, ocid=ocid
            )

        def fetch_job_world():
            if not api_class:
                return None, None
            return get_ranking_snapshot(
                target_date=date_text,
                world_name=world_name,
                character_class=api_class,
                ocid=ocid,
            )

        def fetch_job():
            if not api_class:
                return None, None
            return get_ranking_snapshot(
                target_date=date_text, character_class=api_class, ocid=ocid
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(fetch_overall),
                executor.submit(fetch_world),
                executor.submit(fetch_job_world),
                executor.submit(fetch_job),
            ]
            values = [future.result() for future in futures]

        names = ("ranking", "worldRanking", "jobWorldRanking", "jobRanking")
        result = {name: (data.get("ranking") if data else None)
                  for name, (data, _) in zip(names, values)}
        responses = [response for _, response in values if response is not None]
        has_data = any(result.values())
        has_error = any(response.status_code != 200 for response in responses)
        if has_data and has_error:
            status = "partial"
        elif has_data:
            status = "available"
        elif has_error:
            status = "unavailable"
        else:
            status = "empty"

        result.update({
            "rankingDataStatus": status,
            "rankingDate": date_text,
            "rankingApiStatuses": [response.status_code for response in responses],
        })
        return result

    # 오늘자 집계가 아직 게시되지 않았을 때만 직전 날짜로 대체한다.
    for days_ago in range(0, 3):
        candidate = fetch_for_date(requested_date - timedelta(days=days_ago))
        if candidate["rankingDataStatus"] != "empty":
            return candidate

    return candidate


def is_temporary_nexon_failure(response):
    if response is None:
        return True
    return response.status_code in (408, 425, 429) or response.status_code >= 500
