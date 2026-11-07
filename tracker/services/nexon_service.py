"""Nexon Open API 응답을 애플리케이션 기능에 맞게 조합하는 서비스."""
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MAX_FILTERED_RANKING_PAGES = 25

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


def _find_character_in_filtered_ranking(
    target_date,
    world_name,
    api_class,
    character_class,
    character_name,
    ocid,
    historical=False,
):
    """직업·월드 필터 목록을 페이지 단위로 조회해 대상 캐릭터의 순위를 찾는다.

    OCID를 ranking/overall 요청에 함께 보내면 직업/월드 목록이 아니라
    해당 캐릭터의 단건 결과만 반환될 수 있으므로, 필터 목록 자체에서 찾는다.
    """
    from tracker.integrations.nexon_api import get_ranking_page

    last_response = None
    last_details = {
        "pagesScanned": 0,
        "returnedEntries": 0,
        "filterUsed": api_class,
        "matched": False,
        "pageLimitReached": False,
    }
    if not api_class:
        return None, None, last_details

    # jobs.json의 매핑값이 Nexon API character_class 계약값이다.
    # UI 직업명(character_class)을 두 번째 필터로 재시도하면 같은 직업을
    # 중복 조회하거나, 지원되지 않는 필터값 때문에 불필요한 오류가 발생한다.
    for page in range(1, MAX_FILTERED_RANKING_PAGES + 1):
        entries, response = get_ranking_page(
            target_date=target_date,
            world_name=world_name,
            character_class=api_class,
            page=page,
            historical=historical,
        )
        last_response = response
        last_details = {
            "pagesScanned": page,
            "returnedEntries": len(entries),
            "filterUsed": api_class,
            "matched": False,
        }
        if response is None or response.status_code != 200:
            return None, response, last_details

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_ocid = entry.get("ocid") or entry.get("character_ocid")
            if entry_ocid:
                matches = str(entry_ocid) == str(ocid)
            else:
                # Nexon의 공개 랭킹 목록 응답에는 OCID가 없는 경우가 있다.
                # 전체 직업 랭킹(world_name=None)에서는 월드 조건을 적용하지 않고,
                # 특정 월드 랭킹에서만 월드까지 확인한다.
                entry_name = str(entry.get("character_name") or "").strip().casefold()
                target_name = str(character_name or "").strip().casefold()
                entry_world = str(entry.get("world_name") or "").strip()
                matches = bool(target_name and entry_name == target_name)
                if matches and world_name:
                    matches = entry_world == str(world_name).strip()
            if matches:
                last_details["matched"] = True
                return entry, response, last_details

        if not entries:
            break
    else:
        # Do not silently report a missing rank when the scan stopped at its safety cap.
        last_details["pageLimitReached"] = True

    return None, last_response, last_details


def get_character_rankings(
    target_date, world_name, character_class, ocid, character_name=None
):
    """전체·월드 순위와 동일 직업의 월드·전체 순위를 각각 조회한다.

    전체·월드 순위는 OCID 단건 조회를 사용하고, 직업 순위는 직업 필터가
    적용된 목록에서 OCID/캐릭터 식별 정보를 찾아 실제 해당 목록의 순위를 쓴다.
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
                return None, None, {"pagesScanned": 0, "returnedEntries": 0, "matched": False}
            return _find_character_in_filtered_ranking(
                date_text, world_name, api_class, character_class,
                character_name, ocid,
            )

        def fetch_job():
            if not api_class:
                return None, None, {"pagesScanned": 0, "returnedEntries": 0, "matched": False}
            return _find_character_in_filtered_ranking(
                date_text, None, api_class, character_class,
                character_name, ocid,
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            overall_future = executor.submit(fetch_overall)
            world_future = executor.submit(fetch_world)
            job_world_future = executor.submit(fetch_job_world)
            job_future = executor.submit(fetch_job)
            overall_data, overall_response = overall_future.result()
            world_data, world_response = world_future.result()
            job_world_data, job_world_response, job_world_details = job_world_future.result()
            job_data, job_response, job_details = job_future.result()

        values = [
            (overall_data, overall_response),
            (world_data, world_response),
            (job_world_data, job_world_response),
            (job_data, job_response),
        ]
        names = ("ranking", "worldRanking", "jobWorldRanking", "jobRanking")
        diagnostics = {}
        for name, (data, response) in zip(names, values):
            entry_count = None
            if response is not None and response.status_code == 200:
                try:
                    entry_count = len(response.json().get("ranking", []))
                except (TypeError, ValueError, AttributeError):
                    entry_count = None
            error_code = None
            error_message = None
            if response is not None and response.status_code >= 400:
                try:
                    error_payload = response.json()
                except (TypeError, ValueError, AttributeError):
                    error_payload = {}
                if isinstance(error_payload, dict):
                    error_detail = error_payload.get("error", error_payload)
                    if isinstance(error_detail, dict):
                        error_code = error_detail.get("name") or error_detail.get("code")
                        error_message = error_detail.get("message")
                    elif error_detail:
                        error_message = str(error_detail)
            diagnostics[name] = {
                "statusCode": response.status_code if response is not None else None,
                "returnedEntries": entry_count,
                "matched": data is not None,
                "errorCode": str(error_code)[:80] if error_code else None,
                "errorMessage": str(error_message)[:240] if error_message else None,
            }

        diagnostics["jobWorldRanking"].update(job_world_details)
        diagnostics["jobRanking"].update(job_details)
        result = {
            name: (data.get("ranking") if isinstance(data, dict) else None)
            for name, (data, _) in zip(names, values)
        }
        has_data = any(value is not None for value in result.values())
        http_error = any(
            response is not None and response.status_code != 200
            for _, response in values
        )
        mapping_missing = not bool(api_class)
        filtered_rank_missing = bool(api_class) and (
            result["jobWorldRanking"] is None or result["jobRanking"] is None
        )
        has_error = http_error or mapping_missing or filtered_rank_missing

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
        if filtered_rank_missing:
            warnings.append("동일 직업 랭킹 목록에서 해당 캐릭터를 찾지 못했습니다.")
        if http_error:
            warnings.append("일부 랭킹 API 요청이 정상 응답하지 않았습니다.")
        if not has_data and not http_error:
            counts = ", ".join(
                f"{name}: HTTP {detail['statusCode']} / "
                f"{detail['returnedEntries'] if detail['returnedEntries'] is not None else '응답 파싱 불가'}건"
                for name, detail in diagnostics.items()
            )
            warnings.append("공개 랭킹 응답에 캐릭터 항목이 없습니다. " + counts)

        result.update({
            "rankingDataStatus": status,
            "rankingDate": date_text,
            "rankingApiStatuses": {
                name: detail["statusCode"] for name, detail in diagnostics.items()
            },
            "rankingApiDiagnostics": diagnostics,
            "rankingWarnings": warnings,
        })
        return result

    for days_ago in range(0, 3):
        candidate = fetch_for_date(requested_date - timedelta(days=days_ago))
        if candidate["rankingDataStatus"] == "empty":
            continue

        # 랭킹 집계일 당일에는 공개 API가 아직 날짜를 허용하지 않아
        # HTTP 400을 반환할 수 있다. 이 경우에만 직전 집계일을 재시도한다.
        # 401/403 등 인증·권한 오류는 날짜를 바꿔도 해결되지 않으므로 즉시 반환한다.
        status_codes = [
            status for status in candidate["rankingApiStatuses"].values()
            if status is not None
        ]
        all_bad_request = bool(status_codes) and all(
            status == 400 for status in status_codes
        )
        if all_bad_request and days_ago < 2:
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
