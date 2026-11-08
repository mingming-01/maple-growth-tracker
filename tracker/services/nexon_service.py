"""Nexon Open API 응답을 애플리케이션 기능에 맞게 조합하는 서비스."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from flask import current_app, has_app_context

from tracker.integrations.nexon_api import (
    get_basic_character,
    get_ocid,
    get_ranking,
)


def resolve_character(character_name):
    """캐릭터명으로 OCID와 기본 정보를 순서대로 확인한다."""
    ocid, response = get_ocid(character_name)
    if not ocid:
        return None, None, response
    basic, response = get_basic_character(ocid)
    return ocid, basic, response


def get_basic_character_snapshot(ocid, target_date=None, historical=False):
    return get_basic_character(ocid, target_date=target_date, historical=historical)


def get_ranking_snapshot(
    target_date,
    world_name=None,
    ocid=None,
    character_class=None,
    world_type=0,
    historical=False,
):
    """랭킹 스냅샷을 조회한다. character_class는 API의 class 필터 값이다."""
    return get_ranking(
        target_date=target_date,
        world_name=world_name,
        ocid=ocid,
        character_class=character_class,
        world_type=world_type,
        historical=historical,
    )


def _jobs_path():
    if has_app_context():
        return Path(current_app.root_path) / "static" / "jobs.json"
    return Path(__file__).resolve().parents[2] / "static" / "jobs.json"


def get_api_class(character_class):
    """기본 정보에 직군/전직이 없을 때 사용할 API class 필터를 반환한다."""
    try:
        with _jobs_path().open("r", encoding="utf-8") as file:
            jobs_data = json.load(file)
    except (OSError, ValueError, TypeError):
        return None
    return jobs_data.get(character_class)


def _normalize(value):
    return str(value).strip() if value is not None else ""


def _class_filter_from_entry(entry, fallback_class):
    """랭킹 응답의 직군/전직 값을 우선 사용하고 매핑 파일을 폴백한다."""
    if isinstance(entry, dict):
        family = _normalize(entry.get("class_name"))
        job = _normalize(entry.get("sub_class_name"))
        if family and job:
            return f"{family}-{job}"
    return fallback_class


def _validate_filtered_entry(entry, class_filter, world_name=None):
    """필터 응답의 대상 직업과 월드를 검증한다."""
    if not isinstance(entry, dict):
        return False, "missing_entry"
    family, separator, job = _normalize(class_filter).partition("-")
    actual_family = _normalize(entry.get("class_name"))
    actual_job = _normalize(entry.get("sub_class_name"))
    if not separator or not family or not job or not actual_family:
        return False, "job_metadata_missing"
    if actual_family != family:
        return False, "job_mismatch"
    # '전체 전직'은 직업군 전체를 뜻하므로 세부 전직 이름은 다를 수 있다.
    if job != "전체 전직" and actual_job != job:
        return False, "job_mismatch"
    if world_name and _normalize(entry.get("world_name")) != _normalize(world_name):
        return False, "world_mismatch"
    return True, "verified"


def _response_entry_count(response):
    if response is None or response.status_code != 200:
        return None
    try:
        return len(response.json().get("ranking", []))
    except (TypeError, ValueError, AttributeError):
        return None


def _rank_value(entry):
    if not isinstance(entry, dict):
        return None
    return entry.get("ranking")


def _rank_is_consistent(rank, upper_bound):
    if rank is None or upper_bound is None:
        return True
    try:
        return int(rank) <= int(upper_bound)
    except (TypeError, ValueError):
        return False


def get_world_type(world_name):
    """에오스/헬리오스(구 리부트 계열)는 API의 type 1 랭킹을 사용한다."""
    reboot_worlds = {"에오스", "헬리오스", "리부트", "리부트2"}
    return 1 if _normalize(world_name) in reboot_worlds else 0


def get_character_rankings(target_date, world_name, character_class, ocid):
    """대상 OCID의 종합·월드·직업/월드·직업 순위를 조회한다."""
    fallback_class = get_api_class(character_class)
    try:
        requested_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        requested_date = datetime.now(ZoneInfo("Asia/Seoul")).date()

    def fetch_for_date(date_value):
        date_text = date_value.isoformat()
        world_type = get_world_type(world_name)
        # 직업 필터는 응답의 class_name/sub_class_name으로 만들어야 하므로
        # OCID 단건 종합 랭킹을 먼저 가져와 필터 값을 확정한다.
        overall_data, overall_response = get_ranking_snapshot(
            target_date=date_text, ocid=ocid, world_type=world_type
        )
        api_class = _class_filter_from_entry(overall_data, fallback_class)

        def fetch_world():
            return get_ranking_snapshot(
                target_date=date_text, world_name=world_name, ocid=ocid,
                world_type=world_type,
            )

        def fetch_job_world():
            if not api_class:
                return None, None
            return get_ranking_snapshot(
                target_date=date_text,
                world_name=world_name,
                ocid=ocid,
                character_class=api_class,
                world_type=world_type,
            )

        def fetch_job():
            if not api_class:
                return None, None
            return get_ranking_snapshot(
                target_date=date_text,
                ocid=ocid,
                character_class=api_class,
                world_type=world_type,
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            world_future = executor.submit(fetch_world)
            job_world_future = executor.submit(fetch_job_world)
            job_future = executor.submit(fetch_job)
            world_data, world_response = world_future.result()
            job_world_data, job_world_response = job_world_future.result()
            job_data, job_response = job_future.result()

        entries = {
            "ranking": overall_data,
            "worldRanking": world_data,
            "jobWorldRanking": job_world_data,
            "jobRanking": job_data,
        }
        responses = {
            "ranking": overall_response,
            "worldRanking": world_response,
            "jobWorldRanking": job_world_response,
            "jobRanking": job_response,
        }
        diagnostics = {}
        warnings = []
        for name, entry in entries.items():
            response = responses[name]
            detail = {
                "statusCode": response.status_code if response is not None else None,
                "returnedEntries": _response_entry_count(response),
                "matched": entry is not None,
            }
            if response is not None and response.status_code >= 400:
                try:
                    payload = response.json()
                except (TypeError, ValueError, AttributeError):
                    payload = {}
                error = payload.get("error", {}) if isinstance(payload, dict) else {}
                if isinstance(error, dict):
                    detail["errorCode"] = error.get("name") or error.get("code")
                    detail["errorMessage"] = error.get("message")
            diagnostics[name] = detail

        # filtered endpoints return the target row directly when OCID is supplied.
        for name, entry, requested_world in (
            ("jobWorldRanking", job_world_data, world_name),
            ("jobRanking", job_data, None),
        ):
            if entry is None:
                continue
            valid, reason = _validate_filtered_entry(entry, api_class, requested_world)
            diagnostics[name]["filterValidation"] = reason
            diagnostics[name]["filterUsed"] = api_class
            if not valid:
                entries[name] = None
                diagnostics[name]["matched"] = False
                if reason == "world_mismatch":
                    warnings.append("월드 직업 랭킹의 월드가 요청한 월드와 달라 해당 순위를 제외했습니다.")
                elif reason == "job_mismatch":
                    warnings.append("직업 랭킹 응답이 요청한 직업과 달라 해당 순위를 제외했습니다.")
                else:
                    warnings.append("직업 랭킹 응답의 직업 정보를 검증할 수 없어 해당 순위를 제외했습니다.")

        result = {name: _rank_value(entry) for name, entry in entries.items()}
        consistency_checks = (
            ("jobWorldRanking", "worldRanking"),
            ("jobWorldRanking", "jobRanking"),
            ("jobRanking", "ranking"),
            ("worldRanking", "ranking"),
        )
        for lower, upper in consistency_checks:
            if not _rank_is_consistent(result[lower], result[upper]):
                result[lower] = None
                diagnostics[lower]["rankConsistency"] = "mismatch"
                warnings.append("랭킹 간 순위 관계가 맞지 않아 일부 순위를 제외했습니다.")

        http_error = any(
            response is not None and response.status_code != 200
            for response in responses.values()
        )
        mapping_missing = not api_class
        if mapping_missing:
            warnings.append("직업 랭킹 API 직업명 매핑을 찾지 못했습니다.")
        if any(result[name] is None for name in ("jobWorldRanking", "jobRanking")):
            warnings.append("직업 랭킹 응답에서 해당 캐릭터의 순위를 확인하지 못했습니다.")
        has_data = any(value is not None for value in result.values())
        status = (
            "partial" if has_data and (http_error or mapping_missing or warnings)
            else "available" if has_data
            else "unavailable" if http_error
            else "empty"
        )
        result.update({
            "rankingDataStatus": status,
            "rankingDate": date_text,
            "rankingApiStatuses": {
                name: detail["statusCode"] for name, detail in diagnostics.items()
            },
            "rankingApiDiagnostics": diagnostics,
            "rankingWarnings": list(dict.fromkeys(warnings)),
        })
        return result

    candidate = None
    for days_ago in range(3):
        candidate = fetch_for_date(requested_date - timedelta(days=days_ago))
        if candidate["rankingDataStatus"] == "empty":
            continue
        statuses = [s for s in candidate["rankingApiStatuses"].values() if s is not None]
        # 429/5xx는 날짜를 바꿔도 해결되지 않는 일시적 장애일 수 있다.
        # 이때 전체 4개 랭킹을 재조회하면 제한 상황에서 호출량만 더 증가하므로 중단한다.
        temporary_failure = any(
            status in (408, 425, 429) or status >= 500
            for status in statuses
        )
        if temporary_failure:
            return candidate

        all_bad_request = bool(statuses) and all(status == 400 for status in statuses)
        job_missing = (
            candidate.get("jobWorldRanking") is None
            or candidate.get("jobRanking") is None
        )
        # 날짜별 순위의 일관성을 위해 재시도 시 해당 날짜의 네 순위를 함께 조회한다.
        if days_ago < 2 and (
            all_bad_request
            or (candidate["rankingDataStatus"] == "partial" and job_missing)
        ):
            continue
        return candidate

    candidate["rankingDataStatus"] = "not_ready"
    candidate["rankingWarnings"].append(
        "최근 3일간 공개 랭킹 데이터에서 캐릭터 순위를 확인하지 못했습니다."
    )
    return candidate


def is_temporary_nexon_failure(response):
    if response is None:
        return True
    return response.status_code in (408, 425, 429) or response.status_code >= 500
