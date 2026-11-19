"""최근·과거 성장 기록 HTTP 라우트."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import requests
from flask import Blueprint, jsonify, request

from tracker.domain.growth_calculations import (
    calculate_archive_history_changes,
    calculate_recent_history_changes,
)
from tracker.domain.ai_metrics import build_server_growth_metrics
from tracker.services.history_archive_service import fetch_historical_record
from tracker.services.recent_history_service import (
    _get_cached_current_ranking,
    fetch_recent_history,
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
    CHARACTER_CACHE_TTL,
    KOREA_TIMEZONE,
    get_growth_history_service,
    load_api_snapshot,
    save_api_snapshot,
    set_cache,
    with_data_status,
    get_cache,
    get_cache_timestamp,
    increment_metric,
)

history_bp = Blueprint("history", __name__, url_prefix="/api")


def _attach_growth_metrics(payload, reference_date, period_days, character=None):
    """이력 API에 모든 화면이 공유할 서버 계산 지표를 추가한다."""
    records = payload.get("history") if isinstance(payload, dict) else None
    records = records if isinstance(records, list) else []
    if character is None:
        available = [
            item for item in records
            if isinstance(item, dict) and item.get("recordStatus") == "available"
        ]
        latest = max(available, key=lambda item: str(item.get("date") or ""), default=None)
        character = {"experienceRate": latest.get("experienceRate") if latest else None}
    calculated = build_server_growth_metrics(
        character,
        records,
        reference_date=reference_date,
        period_days=period_days,
    )
    payload["metrics"] = calculated["metrics"]
    payload["periodSummary"] = calculated["periodSummary"]
    return payload


def _load_recent_character_basic_snapshot(character_name, ocid, now=None):
    """직전 캐릭터 조회가 저장한 최신 프로필을 성장 기록 조회에서 재사용한다.

    OCID와 캐릭터명을 모두 확인하고, 캐릭터 캐시 TTL 안에 저장된 스냅샷만
    사용한다. 조건을 만족하지 않으면 호출부가 Nexon 기본 정보 API로 폴백한다.
    """
    snapshot, saved_at = load_api_snapshot(f"character:{character_name}")
    if not isinstance(snapshot, dict) or not saved_at:
        return None

    if str(snapshot.get("ocid") or "") != str(ocid):
        return None

    snapshot_name = str(snapshot.get("characterName") or "").strip()
    world_name = str(snapshot.get("worldName") or "").strip()
    if (
        not snapshot_name
        or snapshot_name.casefold() != str(character_name).strip().casefold()
        or not world_name
    ):
        return None

    try:
        saved_time = datetime.fromisoformat(str(saved_at))
        current_time = now or datetime.now().astimezone()
        if saved_time.tzinfo is None:
            saved_time = saved_time.astimezone()
        age_seconds = (current_time - saved_time).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return None

    if age_seconds < 0 or age_seconds > CHARACTER_CACHE_TTL:
        return None

    return {
        "character_name": snapshot_name,
        "world_name": world_name,
        "character_level": snapshot.get("level"),
        "character_exp": snapshot.get("experience"),
        "character_exp_rate": snapshot.get("experienceRate"),
        "_growthSource": "character/basic",
        "_growthObservedAt": saved_at,
        "ranking": snapshot.get("ranking"),
        "ranking_scope": "overall",
        "ranking_date": snapshot.get("rankingDate"),
        "ranking_data_status": snapshot.get("rankingDataStatus"),
    }


def _verified_overall_rank(record, target_date):
    """종합 랭킹의 범위·실제 집계일·양의 정수 여부를 함께 검증한다."""
    if not isinstance(record, dict):
        return None
    if record.get("rankingScope") != "overall":
        return None
    if record.get("rankingSourceDate") != target_date:
        return None
    value = record.get("ranking")
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        rank = int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return rank if rank > 0 else None


def _stale_history_response(cache_key, character_name, error_message):
    """현재 형식 캐시를 우선 사용하고, 구형 캐시는 순위를 제거해 제공한다."""
    snapshot, saved_at = load_api_snapshot(cache_key)
    if snapshot is not None:
        today = datetime.now(KOREA_TIMEZONE).date()
        if "metrics" not in snapshot or "periodSummary" not in snapshot:
            snapshot = _attach_growth_metrics(dict(snapshot), today, 7)
        return jsonify(with_data_status(snapshot, "stale", saved_at)), 200

    legacy_keys = (
        f"history:rank-overall-v3:{character_name}",
        f"history:rank-overall-v2:{character_name}",
        f"history:{character_name}",
    )
    for legacy_key in legacy_keys:
        legacy_snapshot, legacy_saved_at = load_api_snapshot(legacy_key)
        if not isinstance(legacy_snapshot, dict):
            continue
        legacy_history = legacy_snapshot.get("history")
        if not isinstance(legacy_history, list):
            continue

        sanitized = dict(legacy_snapshot)
        sanitized_history = []
        for record in legacy_history:
            if not isinstance(record, dict):
                sanitized_history.append(record)
                continue
            safe_record = dict(record)
            safe_record["ranking"] = None
            safe_record["rankingScope"] = None
            safe_record["rankingSourceDate"] = None
            safe_record["rankingChange"] = None
            sanitized_history.append(safe_record)
        sanitized["history"] = sanitized_history
        sanitized = _attach_growth_metrics(
            sanitized, datetime.now(KOREA_TIMEZONE).date(), 7
        )
        return jsonify(with_data_status(
            sanitized, "stale", legacy_saved_at
        )), 200

    return jsonify({"error": error_message}), 503


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

    # 이전 캐시에는 과거 집계일의 프로필 랭킹이 오늘 순위로 섞였을 수 있어
    # 정합성 기준을 적용한 새 키로 분리한다.
    cache_key = f"history:rank-overall-v4:{character_name}"
    force_refresh = request.args.get("refresh") == "1"
    cached_history = None if force_refresh else get_cache(cache_key)
    cached_records = cached_history.get("history") if isinstance(cached_history, dict) else None
    cached_ranking_is_current = (
        isinstance(cached_records, list)
        and all(
            isinstance(item, dict)
            and item.get("rankingSourceDate") == item.get("date")
            and (
                item.get("ranking") is None
                or _verified_overall_rank(item, item.get("date")) is not None
            )
            for item in cached_records
        )
    )
    if cached_history is not None and cached_ranking_is_current:
        return jsonify(with_data_status(
            cached_history, "cached", get_cache_timestamp(cache_key)
        ))

    limit_response = api_request_limit_response(force_refresh=force_refresh)
    if limit_response:
        return limit_response

    try:
        if requested_ocid:
            ocid = requested_ocid
            basic = _load_recent_character_basic_snapshot(character_name, ocid)
            if basic is not None:
                # 최근 /api/character 응답의 OCID·이름·월드를 검증해 재사용했으므로
                # 이 요청에서 기본 정보 API를 다시 호출할 필요가 없다.
                response = requests.Response()
                response.status_code = 200
            else:
                basic, response = get_basic_character_snapshot(ocid)
            resolved_name = str((basic or {}).get("character_name") or "").strip()
            if resolved_name and resolved_name.casefold() != character_name.casefold():
                return jsonify({"error": "조회한 캐릭터 이름과 OCID가 일치하지 않습니다."}), 404
        else:
            ocid, basic, response = resolve_character(character_name)
        if not ocid:
            if is_temporary_nexon_failure(response):
                return _stale_history_response(cache_key, character_name, "넥슨 API가 일시적으로 응답하지 않습니다. 잠시 후 다시 시도해주세요."
                )
            return jsonify({"error": "캐릭터 정보를 찾을 수 없거나 조회할 수 없습니다."}), response.status_code

        if not basic:
            if is_temporary_nexon_failure(response):
                return _stale_history_response(cache_key, character_name, "캐릭터 정보를 일시적으로 조회할 수 없습니다. 잠시 후 다시 시도해주세요."
                )
            return jsonify({"error": "캐릭터 정보를 확인할 수 없습니다."}), response.status_code

        # 기본 프로필의 세 성장 필드는 동일한 character/basic 응답에서 왔다.
        # 캐시를 재사용한 경우에는 원래 API 스냅샷 저장 시각을 유지한다.
        basic = dict(basic)
        basic.setdefault("_growthSource", "character/basic")
        basic.setdefault(
            "_growthObservedAt",
            datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        )
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

        dates = [today - timedelta(days=i) for i in range(7)]
        # Nexon API 수집 규칙과 제한된 병렬 실행은 서비스 계층에서 담당한다.
        history = fetch_recent_history(
            dates,
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
            max_workers=3,
        )
    except requests.RequestException:
        return _stale_history_response(cache_key, character_name, "성장 기록 조회 중 넥슨 API 연결에 실패했습니다. 잠시 후 다시 시도해주세요."
        )

    failed_records = [item for item in history if item.get("recordStatus") == "unavailable"]
    if failed_records:
        # 일부 날짜의 API 오류가 있어도 저장된 정상 기록은 계속 표시한다.
        # 사용 가능한 데이터가 하나도 없을 때만 이전 스냅샷으로 폴백한다.
        usable_records = [
            item for item in history
            if item.get("recordStatus") in (None, "available")
            and any(
                item.get(field) is not None
                for field in ("ranking", "level", "experience", "experienceRate")
            )
        ]
        if not usable_records:
            error_message = (
                "성장 기록 조회가 일시적으로 지연되고 있습니다. 잠시 후 다시 시도해주세요."
                if any(item.get("retryable") for item in failed_records)
                else "성장 기록을 정상적으로 가져오지 못했습니다."
            )
            return _stale_history_response(cache_key, character_name, error_message)

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
    history_status = (
        "partial" if failed_records
        else "today_not_ready" if latest_record and latest_record.get("recordStatus") == "not_ready"
        else "complete"
    )
    result = _attach_growth_metrics({
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
    }, today, 7, {"experienceRate": basic.get("character_exp_rate")})

    saved_at = datetime.now().astimezone().isoformat(timespec="seconds")
    # 완전한 기록은 갱신하고, 부분 기록은 기존 스냅샷이 없을 때만 저장한다.
    snapshot_saved_at = save_api_snapshot(
        cache_key,
        result,
        only_if_missing=history_status != "complete",
    )
    if snapshot_saved_at:
        saved_at = snapshot_saved_at

    # 오늘 랭킹이 준비되지 않았다면 30분 대신 5분 후 다시 확인한다.
    cache_ttl = HISTORY_CACHE_TTL if history_status == "complete" else 300
    set_cache(cache_key, result, cache_ttl)
    return jsonify(with_data_status(result, "current", saved_at))


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
        # /api/character에서 최근에 OCID·이름·월드를 확인한 프로필이 있으면
        # 배치마다 같은 기본 정보 API를 다시 호출하지 않는다.
        try:
            verified_basic = _load_recent_character_basic_snapshot(
                character_name, ocid
            )
        except Exception:
            verified_basic = None

        verify_response = None
        if verified_basic is not None:
            increment_metric("history.archive_identity_reused")
        else:
            try:
                verified_basic, verify_response = get_basic_character_snapshot(
                    ocid, historical=True
                )
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
        # A checked-but-missing rate is a completed check, not an uncollected date.
        missing_dates = [
            target_date for target_date in batch_dates
            if (
                target_date.isoformat() not in stored_by_date
                or stored_by_date[target_date.isoformat()].get("recordStatus") in ("not_ready", "unavailable")
                or (
                    stored_by_date[target_date.isoformat()].get("recordStatus") == "available"
                    and (
                        stored_by_date[target_date.isoformat()].get("rankingSourceDate") != target_date.isoformat()
                        or (
                            stored_by_date[target_date.isoformat()].get("ranking") is not None
                            and stored_by_date[target_date.isoformat()].get("rankingScope") != "overall"
                        )
                        or not stored_by_date[target_date.isoformat()].get("experienceRateChecked", False)
                        # 레거시 아카이브 행도 성장 데이터 출처와 수집 시각을 확보하도록 다시 확인한다.
                        or not stored_by_date[target_date.isoformat()].get("growthSource")
                        or not stored_by_date[target_date.isoformat()].get("growthObservedAt")
                    )
                )
            )
        ]
        fetched_records = []

        def fetch_target_date(target_date):
            return fetch_historical_record(
                ocid,
                world_name,
                target_date,
                today,
                saved_record=stored_by_date.get(target_date.isoformat()),
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
                (
                    (start_date + timedelta(days=index)).isoformat() not in stored_by_date
                    or stored_by_date[(start_date + timedelta(days=index)).isoformat()].get("recordStatus") != "available"
                    or stored_by_date[(start_date + timedelta(days=index)).isoformat()].get("rankingSourceDate")
                    != (start_date + timedelta(days=index)).isoformat()
                    or (
                        stored_by_date[(start_date + timedelta(days=index)).isoformat()].get("ranking") is not None
                        and stored_by_date[(start_date + timedelta(days=index)).isoformat()].get("rankingScope") != "overall"
                    )
                    or not stored_by_date[(start_date + timedelta(days=index)).isoformat()].get("experienceRateChecked", False)
                    or not stored_by_date[(start_date + timedelta(days=index)).isoformat()].get("growthSource")
                    or not stored_by_date[(start_date + timedelta(days=index)).isoformat()].get("growthObservedAt")
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
                "ranking": _verified_overall_rank(saved, date_string),
                "rankingScope": (
                    "overall"
                    if _verified_overall_rank(saved, date_string) is not None
                    else None
                ),
                "rankingSourceDate": saved.get("rankingSourceDate"),

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
                "rankingSourceDate": None,
                "recordStatus": "not_collected",
                "recordSource": None
            })

    calculate_archive_history_changes(history)

    available_days = sum(item["recordStatus"] == "available" for item in history)
    not_ready_days = sum(item["recordStatus"] == "not_ready" for item in history)
    not_collected_days = sum(item["recordStatus"] == "not_collected" for item in history)
    response_payload = {
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
    }
    response_payload = _attach_growth_metrics(response_payload, end_date, days)
    return jsonify(response_payload)
