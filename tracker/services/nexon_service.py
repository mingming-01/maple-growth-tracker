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

    오늘자 집계가 아직 비어 있을 때만 직전 2일까지 확인한다.
    인증·호출 제한 등 HTTP 오류를 과거 날짜 재시도로 숨기지는 않는다.
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
        status_codes = {
            name: response.status_code if response is not None else None
            for name, (_, response) in zip(names, values)
        }
        result = {
            name: (data.get("ranking") if isinstance(data, dict) else None)
            for name, (data, _) in zip(names, values)
        }
        has_data = any(value is not None for value in result.values())
        http_error = any(
            code is not None and code != 200
            for code in status_codes.values()
        )
        mapping_missing = not bool(api_class)
        has_error = http_error or mapping_missing

        if has_data and has_error:
            status = "partial"
        elif has_data:
            status = "available"
        elif http_error:
            status = "unavailable"
        else:
            status = "empty"

        warnings = []
        if mapping_missing:
            warnings.append("직업 랭킹 API 직업명 매핑을 찾지 못했습니다.")
        if http_error:
            warnings.append("일부 랭킹 API 요청이 정상 응답하지 않았습니다.")

        result.update({
            "rankingDataStatus": status,
            "rankingDate": date_text,
            "rankingApiStatuses": status_codes,
            "rankingWarnings": warnings,
        })
        return result

    # 오늘자 데이터가 정상 HTTP 응답이지만 비어 있을 때만 과거 집계일을 확인한다.
    for days_ago in range(0, 3):
        candidate = fetch_for_date(requested_date - timedelta(days=days_ago))
        if candidate["rankingDataStatus"] != "empty":
            return candidate

    # 3일 모두 HTTP 200이지만 해당 캐릭터의 랭킹이 비어 있으면
    # API 장애(unavailable)가 아니라 아직 집계되지 않았거나 집계 대상이 아닌 상태다.
    candidate["rankingDataStatus"] = "not_ready"
    candidate["rankingWarnings"].append(
        "최근 3일간 공개 랭킹 데이터에서 캐릭터 순위를 확인하지 못했습니다."
    )
    return candidate


def is_temporary_nexon_failure(response):
    if response is None:
        return True
    return response.status_code in (408, 425, 429) or response.status_code >= 500
