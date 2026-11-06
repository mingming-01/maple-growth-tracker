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


def get_current_combat_power(ocid):
    """현재 적용 상태의 실제 전투력을 Nexon stat API에서 조회한다."""
    try:
        response = request_nexon_api("character/stat", {"ocid": ocid})
        if response.status_code != 200:
            return None
        payload = response.json()
    except (requests.RequestException, ValueError, TypeError):
        return None
    final_stats = payload.get("final_stat", []) if isinstance(payload, dict) else []
    for item in final_stats:
        if not isinstance(item, dict) or str(item.get("stat_name", "")).strip() != "전투력":
            continue
        try:
            value = int(float(str(item.get("stat_value", "")).replace(",", "").strip()))
        except (TypeError, ValueError):
            return None
        return {"value": value, "observedAt": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")}
    return None


def get_character_rankings(target_date, world_name, character_class, ocid):
    """전체·월드·직업·직업 월드 랭킹을 병렬 조회해 결과 상태를 합친다."""
    result = {
        "ranking": None,
        "worldRanking": None,
        "jobWorldRanking": None,
        "jobRanking": None,
        "rankingDataStatus": "not_ready",
        "combatPower": None,
    }
    api_class = get_api_class(character_class)

    def fetch_overall():
        return get_ranking_snapshot(target_date=target_date, ocid=ocid)

    def fetch_world():
        return get_ranking_snapshot(
            target_date=target_date, world_name=world_name, ocid=ocid
        )

    def fetch_job_world():
        if not api_class:
            return None, None
        return get_ranking_snapshot(
            target_date=target_date,
            world_name=world_name,
            character_class=api_class,
            ocid=ocid,
        )

    def fetch_job():
        if not api_class:
            return None, None
        return get_ranking_snapshot(
            target_date=target_date,
            character_class=api_class,
            ocid=ocid,
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(fetch_overall),
            executor.submit(fetch_world),
            executor.submit(fetch_job_world),
            executor.submit(fetch_job),
        ]
        overall_data, overall_response = futures[0].result()
        world_data, world_response = futures[1].result()
        job_world_data, job_world_response = futures[2].result()
        job_data, job_response = futures[3].result()
        combat_power = futures[4].result()

    if overall_data:
        result["ranking"] = overall_data.get("ranking")
    if world_data:
        result["worldRanking"] = world_data.get("ranking")
    if job_world_data:
        result["jobWorldRanking"] = job_world_data.get("ranking")
    if job_data:
        result["jobRanking"] = job_data.get("ranking")
    if combat_power:
        result["combatPower"] = combat_power

    responses = [
        response
        for response in (
            overall_response,
            world_response,
            job_world_response,
            job_response,
        )
        if response is not None
    ]
    has_data = any((overall_data, world_data, job_world_data, job_data))
    has_error = any(response.status_code != 200 for response in responses)

    if has_data and has_error:
        result["rankingDataStatus"] = "partial"
    elif has_data:
        result["rankingDataStatus"] = "available"
    elif has_error:
        result["rankingDataStatus"] = "unavailable"

    return result


def is_temporary_nexon_failure(response):
    if response is None:
        return True
    return response.status_code in (408, 425, 429) or response.status_code >= 500
