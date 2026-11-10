"""캐릭터 정보 조회 HTTP 라우트."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import time

import requests
from flask import Blueprint, current_app, jsonify, request

from tracker.services.nexon_service import (
    get_character_rankings,
    is_temporary_nexon_failure,
    resolve_character,
)
from tracker.services.character_detail_service import get_current_combat_power
from tracker.services.performance_metrics import observe_metric
from tracker.controller.request_limit_helpers import api_request_limit_response
from tracker.runtime import (
    CHARACTER_CACHE_TTL,
    KOREA_TIMEZONE,
    delete_cache,
    get_cache,
    get_cache_timestamp,
    save_api_snapshot,
    set_cache,
    record_best_combat_power,
    stale_snapshot_response,
    with_data_status,
)

character_bp = Blueprint("character", __name__, url_prefix="/api")


def _observe_character_search_component(component, operation):
    """캐릭터 검색에서 병렬 실행되는 독립 작업의 개별 소요 시간을 기록한다."""
    started_at = time.perf_counter()
    try:
        return operation()
    finally:
        observe_metric(
            "character.search_component_ms",
            (time.perf_counter() - started_at) * 1000,
            component=component,
        )


@character_bp.route("/character")
def get_character():
    """캐릭터 기본 정보와 현재 공개 랭킹을 조회한다."""
    character_name = request.args.get("name", "").strip()
    if not character_name:
        return jsonify({"error": "캐릭터 이름을 입력해주세요."}), 400
    if len(character_name) > 30:
        return jsonify({"error": "캐릭터 이름이 너무 깁니다."}), 400

    cache_key = f"character:{character_name}"
    force_refresh = request.args.get("refresh") == "1"
    cached_character = None if force_refresh else get_cache(cache_key)
    if cached_character is not None:
        return jsonify(with_data_status(
            cached_character, "cached", get_cache_timestamp(cache_key)
        ))

    limit_response = api_request_limit_response(force_refresh=force_refresh)
    if limit_response:
        return limit_response

    try:
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

        character_class = basic["character_class"]

        # OCID가 확보된 뒤 랭킹과 메인 프로필 전투력은 서로 독립적으로 조회할 수 있다.
        # Nexon API 전역 호출 간격과 재시도 정책은 그대로 유지한다.
        app = current_app._get_current_object()

        def fetch_rankings():
            return _observe_character_search_component(
                "rankings",
                lambda: get_character_rankings(
                    target_date=datetime.now(KOREA_TIMEZONE).strftime("%Y-%m-%d"),
                    world_name=basic["world_name"],
                    character_class=character_class,
                    ocid=ocid,
                ),
            )

        def fetch_current_combat_power():
            def fetch():
                with app.app_context():
                    return get_current_combat_power(
                        ocid, force_refresh=force_refresh
                    )
            return _observe_character_search_component("combat_power", fetch)

        parallel_started_at = time.perf_counter()
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                rankings_future = executor.submit(fetch_rankings)
                combat_power_future = executor.submit(fetch_current_combat_power)
                character_rankings = rankings_future.result()
                current_combat_power = combat_power_future.result()
        finally:
            observe_metric(
                "character.search_parallel_ms",
                (time.perf_counter() - parallel_started_at) * 1000,
            )

        best_power = record_best_combat_power(ocid, current_combat_power) or {}
        if current_combat_power is not None:
            # 새 전투력과 이전 상세 응답 캐시가 함께 남지 않도록 스탯 응답만 무효화한다.
            delete_cache(f"character-details:{ocid}:stats")
    except requests.RequestException:
        return stale_snapshot_response(
            cache_key, "넥슨 API 연결에 실패했습니다. 잠시 후 다시 시도해주세요."
        )

    result = {
        "characterName": basic["character_name"],
        "character_image": basic.get("character_image"),
        "worldName": basic["world_name"],
        "job": character_class,
        "guildName": basic.get("character_guild_name"),
        "level": basic["character_level"],
        "experience": basic["character_exp"],
        "experienceRate": basic["character_exp_rate"],
        "ranking": character_rankings["ranking"],
        "worldRanking": character_rankings["worldRanking"],
        "jobWorldRanking": character_rankings["jobWorldRanking"],
        "jobRanking": character_rankings["jobRanking"],
        "rankingExperience": basic["character_exp"],
        "ocid": ocid,
        "rankingDataStatus": character_rankings["rankingDataStatus"],
        "rankingDate": character_rankings.get("rankingDate"),
        "rankingApiStatuses": character_rankings.get("rankingApiStatuses", {}),
        "rankingApiDiagnostics": character_rankings.get("rankingApiDiagnostics", {}),
        "rankingWarnings": character_rankings.get("rankingWarnings", []),
        "currentCombatPower": current_combat_power,
        "bestCombatPower": best_power.get("value"),
        "bestCombatPowerObservedAt": best_power.get("observedAt"),
        "bestPresetCombination": best_power.get("presetNumbers"),
    }

    data_status = "partial" if character_rankings["rankingDataStatus"] in ("partial", "unavailable", "empty", "not_ready") else "current"
    saved_at = datetime.now().astimezone().isoformat(timespec="seconds")

    # 부분 응답은 기존 정상 스냅샷을 보호하고, 저장된 값이 없을 때만 최초 기록한다.
    snapshot_saved_at = save_api_snapshot(
        cache_key,
        result,
        only_if_missing=character_rankings["rankingDataStatus"] != "available",
    )
    if snapshot_saved_at:
        saved_at = snapshot_saved_at

    set_cache(cache_key, result, CHARACTER_CACHE_TTL)
    return jsonify(with_data_status(result, data_status, saved_at))
