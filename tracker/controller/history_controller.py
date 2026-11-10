"""최근·과거 성장 기록 HTTP 라우트."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import requests
from flask import Blueprint, jsonify, request

from tracker.domain.growth_calculations import (
    calculate_archive_history_changes,
    calculate_recent_history_changes,
)
from tracker.services.nexon_service import (
    get_basic_character_snapshot,
    get_ranking_snapshot,
    get_world_type,
    is_temporary_nexon_failure,
    resolve_character,
)
from tracker.controller.request_limit_helpers import api_request_limit_response
from tracker.runtime import (
    HISTORY_BACKFILL_BATCH_SIZE,
    HISTORY_CACHE_TTL,
    KOREA_TIMEZONE,
    get_growth_history_service,
    load_api_snapshot,
    save_api_snapshot,
    set_cache,
    stale_snapshot_response,
    with_data_status,
    get_cache,
    get_cache_timestamp,
)

history_bp = Blueprint("history", __name__, url_prefix="/api")


# 최근 7일 성장 기록 조회 및 변화량 계산
@history_bp.route("/history")
def get_history():
    """기본 검색에서 최근 7일의 성장 기록을 조회하고 저장한다."""
    growth_history_service = get_growth_history_service()
    character_name = request.args.get("name", "").strip()
    if not character_name:
        return jsonify({"error": "캐릭터 이름을 입력해주세요."}), 400
    if len(character_name) > 30:
        return jsonify({"error": "캐릭터 이름이 너무 깁니다."}), 400

    requested_ocid = request.args.get("ocid", "").strip()
    if len(requested_ocid) > 128:
        return jsonify({"error": "캐릭터 식별 정보가 올바르지 않습니다."}), 400

    cache_key = f"history:{character_name}"
    force_refresh = request.args.get("refresh") == "1"
    cached_history = None if force_refresh else get_cache(cache_key)
    if cached_history is not None:
        return jsonify(with_data_status(
            cached_history, "cached", get_cache_timestamp(cache_key)
        ))

    limit_response = api_request_limit_response(force_refresh=force_refresh)
    if limit_response:
        return limit_response

    try:
        if requested_ocid:
            ocid = requested_ocid
            basic, response = get_basic_character_snapshot(ocid)
            resolved_name = str((basic or {}).get("character_name") or "").strip()
            if resolved_name and resolved_name.casefold() != character_name.casefold():
                return jsonify({"error": "조회한 캐릭터 이름과 OCID가 일치하지 않습니다."}), 404
        else:
            ocid, basic, response = resolve_character(character_name)
        if not ocid:
            if is_temporary_nexon_failure(response):
                return stale_snapshot_response(
                    cache_key, "넥슨 API가 일시적으로 응답하지 않습니다. 잠시 후 다시 시도해주세요."
                )
            return jsonify({"error": "캐릭터 정보를 찾을 수 없거나 조회할 수 없습니다."}), response.status_code

        if not basic:
            if is_temporary_nexon_failure(response):
                return stale_snapshot_response(
                    cache_key, "캐릭터 정보를 일시적으로 조회할 수 없습니다. 잠시 후 다시 시도해주세요."
                )
            return jsonify({"error": "캐릭터 정보를 확인할 수 없습니다."}), response.status_code

        world_name = basic["world_name"]
        today = datetime.now(KOREA_TIMEZONE).date()
        stored_recent = {}
        try:
            stored_records = growth_history_service.get_records(
                ocid, today - timedelta(days=6), today
            )
            stored_recent = {item["date"]: item for item in stored_records}
        except Exception:
            # DB 연결 문제는 실시간 API 조회를 막지 않는다.
            print("저장된 성장 기록을 불러오지 못했습니다.")

        def fetch_history(target_date):
            date_string = target_date.strftime("%Y-%m-%d")
            saved = stored_recent.get(date_string)
            # 정상 스냅샷이 아닌 저장 기록은 다음 새로고침에서 재확인한다.
            # not_ready를 오래 고정해 성장 기록이 영구적으로 비는 현상을 방지한다.
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
                    "_fromStore": True
                }

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
                    "recordStatus": "available"
                }

            # 랭킹 API가 429/5xx 등 일시적 오류를 반환했다면 기본 정보 API를
            # 연쇄 호출하지 않는다. 제한 상황에서 요청량이 더 커지는 것을 방지한다.
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
                        "_fromStore": True
                    }
                return {
                    "date": date_string,
                    "ranking": None,
                    "level": None,
                    "experience": None,
                    "experienceRate": None,
                    "experienceRateChecked": False,
                    "recordStatus": "unavailable",
                    "retryable": True
                }

            # 정상 응답으로 랭킹 항목이 없을 때만 기본 정보 API를 보조 조회한다.
            try:
                basic_data, basic_response = get_basic_character_snapshot(
                    ocid,
                    target_date=date_string if target_date < today else None,
                    historical=True
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
                        "recordStatus": "available"
                    }

            # 빈 응답으로 같은 날 앞서 저장한 정상 스냅샷을 덮어쓰지 않는다.
            if saved and saved.get("recordStatus") == "available":
                return {
                    "date": date_string,
                    "ranking": saved.get("ranking"),
                    "level": saved.get("level"),
                    "experience": saved.get("experience"),
                    "experienceRate": saved.get("experienceRate"),
                    "experienceRateChecked": saved.get("experienceRateChecked", False),
                    "recordStatus": "available",
                    "_fromStore": True
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
                    "experienceRateChecked": bool(basic_response is not None and basic_response.status_code == 200),
                    "recordStatus": "not_ready"
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
                "retryable": retryable
            }

        dates = [today - timedelta(days=i) for i in range(7)]
        # Historical snapshots are rate-limited upstream; keep a small bounded
        # worker pool instead of launching seven simultaneous date lookups.
        with ThreadPoolExecutor(max_workers=3) as executor:
            history = list(executor.map(fetch_history, dates))
        history.reverse()
    except requests.RequestException:
        return stale_snapshot_response(
            cache_key, "성장 기록 조회 중 넥슨 API 연결에 실패했습니다. 잠시 후 다시 시도해주세요."
        )

    failed_records = [item for item in history if item.get("recordStatus") == "unavailable"]
    if failed_records:
        # 여러 날짜를 병렬 조회하므로 일시적 오류와 확정 오류가 섞일 수 있다.
        # 하나라도 429/5xx/네트워크 오류가 있으면 전체 결과를 502로 단정하지 않고
        # 저장된 정상 스냅샷을 우선 제공하거나 재시도 가능한 503으로 응답한다.
        if any(item.get("retryable") for item in failed_records):
            return stale_snapshot_response(
                cache_key, "성장 기록 조회가 일시적으로 지연되고 있습니다. 잠시 후 다시 시도해주세요."
            )
        return jsonify({"error": "성장 기록을 정상적으로 가져오지 못했습니다."}), 502

    calculate_recent_history_changes(history)

    records_to_save = [item for item in history if not item.get("_fromStore")]
    try:
        saved_record_count = growth_history_service.save_records(
            ocid, basic["character_name"], world_name, records_to_save
        )
        storage_status = "saved" if saved_record_count else "no_new_records"
    except Exception:
        # 저장소 장애가 있어도 현재 캐릭터 화면은 계속 표시한다.
        print("성장 기록을 장기 저장하지 못했습니다.")
        saved_record_count = 0
        storage_status = "unavailable"

    for item in history:
        item.pop("_fromStore", None)

    experience_changes = [
        item["experienceChange"]
        for item in history
        if item.get("experienceChange") is not None
    ]
    average_experience = sum(experience_changes) / len(experience_changes) if experience_changes else None
    latest_record = history[-1] if history else None
    history_status = "today_not_ready" if latest_record and latest_record.get("recordStatus") == "not_ready" else "complete"
    result = {
        "characterName": basic["character_name"],
        "worldName": world_name,
        "level": basic["character_level"],
        "history": history,
        "averageDailyExperience": average_experience,
        "historyStatus": history_status,
        "historyStorage": {
            "backend": growth_history_service.backend,
            "status": storage_status,
            "savedRecords": saved_record_count
        }
    }

    saved_at = datetime.now().astimezone().isoformat(timespec="seconds")
    previous_snapshot, _ = load_api_snapshot(cache_key)
    if history_status == "complete" or previous_snapshot is None:
        snapshot_saved_at = save_api_snapshot(cache_key, result)
        if snapshot_saved_at:
            saved_at = snapshot_saved_at

    # 오늘 랭킹이 준비되지 않았다면 30분 대신 5분 후 다시 확인한다.
    cache_ttl = HISTORY_CACHE_TTL if history_status == "complete" else 300
    set_cache(cache_key, result, cache_ttl)
    return jsonify(with_data_status(result, "current", saved_at))


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


@history_bp.route("/history/archive")
def get_history_archive():
    """30일·90일 기록을 조회하고 사용자가 요청한 범위에서 누락 기록을 보충한다."""
    growth_history_service = get_growth_history_service()
    ocid = request.args.get("ocid", "").strip()
    try:
        days = int(request.args.get("days", "30"))
    except (TypeError, ValueError):
        return jsonify({"error": "조회 기간은 30일 또는 90일이어야 합니다."}), 400

    if not ocid or len(ocid) > 128:
        return jsonify({"error": "캐릭터 식별자를 확인해주세요."}), 400
    if days not in (30, 90):
        return jsonify({"error": "조회 기간은 30일 또는 90일이어야 합니다."}), 400

    today = datetime.now(KOREA_TIMEZONE).date()
    end_date_text = request.args.get("end", "").strip()
    end_date = today
    if end_date_text:
        try:
            end_date = date.fromisoformat(end_date_text)
        except ValueError:
            return jsonify({"error": "조회 종료일은 YYYY-MM-DD 형식이어야 합니다."}), 400

        # 기간 비교에는 바로 앞의 동일 길이 기간만 필요하다.
        if end_date > today or end_date < today - timedelta(days=days * 2):
            return jsonify({"error": "조회 종료일은 최근 비교 가능한 기간 안에서 선택해주세요."}), 400

    start_date = end_date - timedelta(days=days - 1)
    try:
        stored_records = growth_history_service.get_records(ocid, start_date, end_date)
    except Exception:
        print("날짜별 성장 기록을 조회하지 못했습니다.")
        return jsonify({"error": "저장된 성장 기록을 조회할 수 없습니다. 저장소 연결을 확인해주세요."}), 503

    stored_by_date = {item["date"]: item for item in stored_records}
    collection = None

    # 과거 데이터는 사용자가 30일·90일 기록을 요청한 경우에만 수집한다.
    if request.args.get("collect") == "1":
        if end_date != today:
            return jsonify({"error": "과거 기록 수집은 최근 30일·90일 범위에서만 가능합니다."}), 400
        character_name = request.args.get("character_name", "").strip()[:30]
        world_name = request.args.get("world_name", "").strip()[:100] or None
        try:
            offset = int(request.args.get("offset", "0"))
            limit = int(request.args.get("limit", str(HISTORY_BACKFILL_BATCH_SIZE)))
        except (TypeError, ValueError):
            return jsonify({"error": "수집 범위를 확인해주세요."}), 400

        if not character_name:
            return jsonify({"error": "캐릭터명을 확인해주세요."}), 400
        if offset < 0 or offset >= days or limit < 1 or limit > HISTORY_BACKFILL_BATCH_SIZE:
            return jsonify({"error": "수집 범위는 날짜 1~10개 안에서 선택해주세요."}), 400

        # 보충 수집은 여러 날짜의 Nexon API를 호출하므로 일반 조회와 별도 갱신 한도를 적용한다.
        limit_response = api_request_limit_response(force_refresh=True)
        if limit_response:
            return limit_response

        # 브라우저에서 전달한 캐릭터명과 OCID를 확인해 다른 캐릭터 기록의 혼합 저장을 막는다.
        try:
            verified_basic, verify_response = get_basic_character_snapshot(ocid, historical=True)
        except requests.RequestException:
            verified_basic, verify_response = None, None

        if not verified_basic:
            if is_temporary_nexon_failure(verify_response):
                return jsonify({"error": "캐릭터 정보를 확인할 수 없습니다. 잠시 후 다시 시도해주세요."}), 503
            return jsonify({"error": "캐릭터 식별 정보를 확인할 수 없습니다."}), 400

        if verified_basic.get("character_name", "").casefold() != character_name.casefold():
            return jsonify({"error": "캐릭터명과 식별 정보가 일치하지 않습니다."}), 400

        character_name = verified_basic["character_name"]
        world_name = verified_basic.get("world_name") or world_name
        batch_dates = [
            start_date + timedelta(days=index)
            for index in range(offset, min(offset + limit, days))
        ]
        missing_dates = [
            target_date for target_date in batch_dates
            if target_date.isoformat() not in stored_by_date
            or stored_by_date[target_date.isoformat()].get("recordStatus") == "not_ready"
            or (
                stored_by_date[target_date.isoformat()].get("recordStatus") == "available"
                and (
                    not stored_by_date[target_date.isoformat()].get("experienceRateChecked", False)
                    or stored_by_date[target_date.isoformat()].get("experienceRate") is None
                )
            )
        ]
        fetched_records = []

        def fetch_target_date(target_date):
            return fetch_historical_record(
                ocid, world_name, target_date, today
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            fetched_records = [
                item for item in executor.map(fetch_target_date, missing_dates)
                if item is not None
            ]

        try:
            saved_count = growth_history_service.save_records(
                ocid, character_name, world_name, fetched_records
            ) if fetched_records else 0
        except Exception:
            print("날짜별 과거 기록을 저장하지 못했습니다.")
            return jsonify({"error": "과거 기록을 저장할 수 없습니다. 저장소 연결을 확인해주세요."}), 503

        for item in fetched_records:
            stored_by_date[item["date"]] = item

        collection = {
            "offset": offset,
            "limit": limit,
            "checkedDays": len(missing_dates),
            "savedRecords": saved_count,
            "availableRecords": sum(item.get("recordStatus") == "available" for item in fetched_records),
            "noDataRecords": sum(item.get("recordStatus") == "not_ready" for item in fetched_records),
            "remainingDays": sum(
                (start_date + timedelta(days=index)).isoformat() not in stored_by_date
                or stored_by_date[(start_date + timedelta(days=index)).isoformat()].get("recordStatus") != "available"
                or (
                    stored_by_date[(start_date + timedelta(days=index)).isoformat()].get("recordStatus") == "available"
                    and (
                        not stored_by_date[(start_date + timedelta(days=index)).isoformat()].get("experienceRateChecked", False)
                        or stored_by_date[(start_date + timedelta(days=index)).isoformat()].get("experienceRate") is None
                    )
                )
                for index in range(days)
            )
        }

    # 중간 수집 배치는 전체 기간 기록을 반복 반환하지 않고 진행 요약만 전달한다.
    # 프론트엔드는 모든 배치가 끝난 뒤 collect 없이 한 번만 전체 기록을 조회한다.
    if request.args.get("summary_only") == "1" and request.args.get("collect") == "1":
        return jsonify({
            "ocid": ocid,
            "days": days,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "collection": collection,
            "storageBackend": growth_history_service.backend,
            "persistentStorage": growth_history_service.uses_postgres,
        })

    history = []
    for offset in range(days):
        target_date = start_date + timedelta(days=offset)
        date_string = target_date.isoformat()
        saved = stored_by_date.get(date_string)
        if saved:
            history.append({
                "date": date_string,
                "ranking": saved.get("ranking"),
                "level": saved.get("level"),
                "experience": saved.get("experience"),
                "experienceRate": saved.get("experienceRate"),
                "experienceRateChecked": saved.get("experienceRateChecked", False),
                "recordStatus": saved.get("recordStatus"),
                "recordSource": "stored"
            })
        else:
            history.append({
                "date": date_string,
                "ranking": None,
                "level": None,
                "experience": None,
                "experienceRate": None,
                "experienceRateChecked": False,
                "recordStatus": "not_collected",
                "recordSource": None
            })

    calculate_archive_history_changes(history)

    available_days = sum(item["recordStatus"] == "available" for item in history)
    not_ready_days = sum(item["recordStatus"] == "not_ready" for item in history)
    not_collected_days = sum(item["recordStatus"] == "not_collected" for item in history)
    return jsonify({
        "ocid": ocid,
        "days": days,
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "history": history,
        "availableDays": available_days,
        "notReadyDays": not_ready_days,
        "notCollectedDays": not_collected_days,
        "collection": collection,
        "storageBackend": growth_history_service.backend,
        "persistentStorage": growth_history_service.uses_postgres
    })
