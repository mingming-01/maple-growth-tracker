"""캐릭터 상세 정보 탭의 지연 조회 API."""
from flask import Blueprint, jsonify, request
from datetime import datetime

from tracker.runtime import get_cache, set_cache, record_best_combat_power, KOREA_TIMEZONE
from tracker.services.character_detail_service import (
    VALID_SECTIONS,
    get_character_detail_section,
)

character_detail_bp = Blueprint(
    "character_detail", __name__, url_prefix="/api"
)

DETAIL_CACHE_TTL = 300


@character_detail_bp.route("/character-details")
def get_character_details():
    """선택된 상세 탭만 조회하며, 일부 API 실패는 기본 검색에 영향을 주지 않는다."""
    ocid = request.args.get("ocid", "").strip()
    section = request.args.get("section", "").strip().lower()
    if not ocid or len(ocid) > 128:
        return jsonify({"error": "캐릭터 식별 정보가 올바르지 않습니다."}), 400
    if section not in VALID_SECTIONS:
        return jsonify({"error": "지원하지 않는 상세 정보 구분입니다."}), 400

    cache_key = f"character-details:{ocid}:{section}"
    force_refresh = request.args.get("refresh") == "1"
    cached = None if force_refresh else get_cache(cache_key)
    if cached is not None:
        result = dict(cached)
        result["dataStatus"] = "cached"
        return jsonify(result)

    result = get_character_detail_section(ocid, section, force_refresh=force_refresh)
    if section == "stats":
        sources = result.get("sources", [])
        stat_source = next((source for source in sources if source.get("id") == "stat"), {})
        preset_keys = {
            "itemEquipment": "equipment", "hyperStat": "hyperStat",
            "ability": "ability", "linkSkill": "link", "unionRaider": "union",
        }
        preset_numbers = {
            preset_keys[source.get("id")]: source.get("activePresetNo")
            for source in sources
            if source.get("id") in preset_keys and source.get("activePresetNo") is not None
        }
        best = record_best_combat_power(
            ocid, stat_source.get("combatPower"),
            preset_numbers=preset_numbers or None,
            observed_at=datetime.now(KOREA_TIMEZONE).isoformat(timespec="seconds"),
        )
        if best:
            result["bestCombatPower"] = best.get("value")
            result["bestCombatPowerObservedAt"] = best.get("observedAt")
            result["bestPresetCombination"] = best.get("presetNumbers")
    result["dataStatus"] = "current"
    set_cache(cache_key, result, DETAIL_CACHE_TTL)
    return jsonify(result)
