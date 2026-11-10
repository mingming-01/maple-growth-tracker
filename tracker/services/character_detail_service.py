"""Nexon Open API 캐릭터 상세 데이터 조회 및 프리셋 정규화."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import json
import time

import requests

from tracker.integrations.nexon_api import request_nexon_api


SECTION_SOURCES = {
    "stats": [
        {"id": "stat", "label": "주요 스탯", "endpoint": "character/stat"},
        {"id": "hyperStat", "label": "하이퍼 스탯", "endpoint": "character/hyper-stat",
         "preset_prefix": "hyper_stat_preset_", "active_fields": ("use_preset_no",),
         "current_fields": ("hyper_stat",), "preset_count": 3},
        {"id": "ability", "label": "어빌리티", "endpoint": "character/ability",
         "preset_prefix": "ability_preset_", "active_fields": ("preset_no",),
         "current_fields": ("ability_info",), "preset_count": 3},
    ],
    "equipment": [
        {"id": "characterAppearance", "label": "헤어·성형·피부", "endpoint": "character/beauty-equipment",
         "current_fields": ("character_hair", "character_face", "character_skin_name")},
        {"id": "itemEquipment", "label": "장비", "endpoint": "character/item-equipment",
         "preset_prefix": "item_equipment_preset_", "active_fields": ("preset_no",),
         "current_fields": ("item_equipment",),
         "preset_count": 3},
        {"id": "androidEquipment", "label": "안드로이드", "endpoint": "character/android-equipment",
         "current_fields": ("android_name", "android_nickname", "android_icon",
                            "android_description", "android_gender", "android_grade",
                            "android_non_humanoid", "android_ear_sensor", "android_hair",
                            "android_face", "android_skin_name")},
        {"id": "setEffect", "label": "세트 효과", "endpoint": "character/set-effect",
         "current_fields": ("set_effect",)},
        {"id": "cashItemEquipment", "label": "캐시 장비 및 외형 프리셋",
         "endpoint": "character/cashitem-equipment",
         "preset_groups": ("cash_item_equipment_preset_", "additional_cash_item_equipment_preset_"),
         "active_fields": ("preset_no",),
         "current_fields": ("cash_item_equipment_base", "additional_cash_item_equipment_base",
                            "character_look_mode", "character_gender", "character_class"),
         "preset_count": 3},
        {"id": "petEquipment", "label": "펫 정보", "endpoint": "character/pet-equipment",
         "current_fields": ("pet_1_name", "pet_1_nickname", "pet_1_icon", "pet_1_description",
                            "pet_1_equipment", "pet_1_auto_skill", "pet_1_pet_type",
                            "pet_2_name", "pet_2_nickname", "pet_2_icon", "pet_2_description",
                            "pet_2_equipment", "pet_2_auto_skill", "pet_2_pet_type",
                            "pet_3_name", "pet_3_nickname", "pet_3_icon", "pet_3_description",
                            "pet_3_equipment", "pet_3_auto_skill", "pet_3_pet_type")},
    ],
    "symbols": [
        {"id": "symbolEquipment", "label": "심볼", "endpoint": "character/symbol-equipment",
         "current_fields": ("symbol",)},
    ],
    "link": [
        {"id": "linkSkill", "label": "링크 스킬", "endpoint": "character/link-skill",
         "preset_groups": ("character_link_skill_preset_", "character_owned_link_skill_preset_"),
         "active_fields": ("use_preset_no", "character_link_skill_preset_no"),
         "current_fields": ("character_link_skill", "character_owned_link_skill"), "preset_count": 3},
    ],
    "union": [
        {"id": "union", "label": "유니온 기본 정보", "endpoint": "user/union"},
        {"id": "unionStateStat", "label": "유니온 스탯", "endpoint": "user/union-raider",
         "preset_list_field": "union_state_stat_preset",
         "preset_number_field": "preset_no",
         "preset_data_field": "union_state_stat",
         "current_fields": ("union_state_stat",),
         "exclude_fields": ("union_raider_stat", "union_occupied_stat", "union_inner_stat",
                            "union_block", "use_preset_no")},
        {"id": "unionArtifact", "label": "유니온 아티팩트", "endpoint": "user/union-artifact",
         "current_fields": ("union_artifact_effect", "union_artifact_crystal",
                            "union_artifact_remain_ap")},
        {"id": "unionChampion", "label": "유니온 챔피언", "endpoint": "user/union-champion",
         "current_fields": ("union_champion", "champion_badge_total_info")},
    ],
    "skills": [
        {"id": "skill6", "label": "6차 스킬", "endpoint": "character/skill",
         "params": {"character_skill_grade": "6"}},
        {"id": "hexaMatrix", "label": "HEXA 코어", "endpoint": "character/hexamatrix"},
        {"id": "hexaStat", "label": "HEXA 스탯", "endpoint": "character/hexamatrix-stat"},
    ],
}

VALID_SECTIONS = frozenset(SECTION_SOURCES)
_SOURCE_CACHE = {}
_SOURCE_CACHE_LOCK = Lock()
_SOURCE_CACHE_TTL = 300


def _has_data(value):
    return value is not None and value != [] and value != {}


def _active_preset(payload, fields):
    for field in fields:
        value = payload.get(field)
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return None


_PRESET_DATA_KEYS = {
    "item_equipment_preset_": "item_equipment",
    "cash_item_equipment_preset_": "cash_item_equipment",
    "additional_cash_item_equipment_preset_": "additional_cash_item_equipment",
    "hyper_stat_preset_": "hyper_stat",
    "ability_preset_": "ability_info",
    "character_link_skill_preset_": "character_link_skill",
    "character_owned_link_skill_preset_": "character_owned_link_skill",
}


def _preset_data_key(prefix):
    return _PRESET_DATA_KEYS.get(prefix, prefix.rstrip("_"))


def _normalize_source(payload, spec):
    """Nexon 원본 응답을 화면에서 사용하는 공통 데이터 구조로 정규화한다."""
    payload = payload if isinstance(payload, dict) else {}

    preset_list_field = spec.get("preset_list_field")
    if preset_list_field:
        number_field = spec.get("preset_number_field", "preset_no")
        value_field = spec.get("preset_data_field", "union_state_stat")
        presets = []
        rows = payload.get(preset_list_field)
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                try:
                    number = int(row.get(number_field))
                except (TypeError, ValueError):
                    continue
                values = row.get(value_field)
                if not isinstance(values, list):
                    values = []
                selected = {value_field: values}
                presets.append({"number": number, "data": selected})

        current_fields = spec.get("current_fields", ())
        current_data = {
            field: payload[field]
            for field in current_fields
            if _has_data(payload.get(field))
        }
        active_number = None
        current_values = current_data.get(value_field)
        if isinstance(current_values, list) and presets:
            current_signature = json.dumps(
                sorted(str(value) for value in current_values),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            matching_numbers = []
            for preset in presets:
                preset_values = preset["data"].get(value_field, [])
                preset_signature = json.dumps(
                    sorted(str(value) for value in preset_values),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                if current_signature == preset_signature:
                    matching_numbers.append(preset["number"])
            if len(matching_numbers) == 1:
                active_number = matching_numbers[0]

        if not presets and current_data:
            presets = [{"number": 0, "data": current_data, "currentOnly": True}]
            active_number = 0

        excluded = set(current_fields) | {preset_list_field} | set(spec.get("exclude_fields", ()))
        data = {key: value for key, value in payload.items() if key not in excluded}
        return {
            "status": "available" if data or presets or current_data else "empty",
            "activePresetNo": active_number,
            "presets": presets,
            "currentData": current_data,
            "data": data,
            "combatPower": _extract_combat_power(payload),
        }

    prefixes = list(spec.get("preset_groups", ()))
    if spec.get("preset_prefix"):
        prefixes.append(spec["preset_prefix"])

    presets = []
    for number in range(1, int(spec.get("preset_count", 0)) + 1):
        selected = {}
        for prefix in prefixes:
            field = f"{prefix}{number}"
            value = payload.get(field)
            if _has_data(value):
                if prefix == "ability_preset_" and isinstance(value, dict):
                    selected["ability_info"] = value.get("ability_info") or []
                    selected["ability_grade"] = (
                        value.get("ability_preset_grade") or value.get("ability_grade")
                    )
                elif prefix == "hyper_stat_preset_":
                    selected["hyper_stat"] = value if isinstance(value, list) else []
                    remain_key = "{}{}_remain_point".format(prefix, number)
                    if remain_key in payload:
                        selected["remain_point"] = payload.get(remain_key)
                else:
                    selected[_preset_data_key(prefix)] = value
        if selected:
            presets.append({"number": number, "data": selected})

    current_fields = spec.get("current_fields", ())
    current_data = {
        field: payload[field]
        for field in current_fields
        if _has_data(payload.get(field))
    }
    if not presets and current_data:
        presets = [{"number": 0, "data": current_data, "currentOnly": True}]

    excluded = set(current_fields) | set(spec.get("active_fields", ()))
    for prefix in prefixes:
        excluded.update(key for key in payload if key.startswith(prefix))
    data = {
        key: value
        for key, value in payload.items()
        if key not in excluded and not key.startswith("preset_")
    }

    return {
        "status": "available" if data or presets or current_data else "empty",
        "activePresetNo": _active_preset(payload, spec.get("active_fields", ())),
        "presets": presets,
        "currentData": current_data,
        "data": data,
        "combatPower": _extract_combat_power(payload),
    }


def _extract_combat_power(payload):
    final_stats = payload.get("final_stat") if isinstance(payload, dict) else None
    if not isinstance(final_stats, list):
        return None
    for item in final_stats:
        if isinstance(item, dict) and str(item.get("stat_name", "")).strip() == "전투력":
            return item.get("stat_value")
    return None


_CHAMPION_IMAGE_CACHE = {}
_CHAMPION_IMAGE_CACHE_LOCK = Lock()
_CHAMPION_IMAGE_CACHE_TTL = 43200


def _fetch_champion_profile(character_name):
    """챔피언 캐릭터의 공식 이미지·직업·레벨을 조회하고 12시간 캐시한다."""
    name = str(character_name or "").strip()
    if not name:
        return {}
    now = time.monotonic()
    with _CHAMPION_IMAGE_CACHE_LOCK:
        cached = _CHAMPION_IMAGE_CACHE.get(name)
        if cached and cached["expires_at"] > now:
            return dict(cached.get("profile") or {})

    profile = {}
    try:
        id_response = request_nexon_api("id", {"character_name": name})
        if id_response.status_code == 200:
            ocid = (id_response.json() or {}).get("ocid")
            if ocid:
                basic_response = request_nexon_api("character/basic", {"ocid": ocid})
                if basic_response.status_code == 200:
                    basic = basic_response.json() or {}
                    profile = {
                        "character_image": basic.get("character_image"),
                        "character_level": basic.get("character_level"),
                        "character_class": basic.get("character_class"),
                        "character_world_name": basic.get("world_name"),
                    }
    except (requests.RequestException, ValueError, TypeError):
        profile = {}

    with _CHAMPION_IMAGE_CACHE_LOCK:
        _CHAMPION_IMAGE_CACHE[name] = {
            "profile": profile,
            "expires_at": time.monotonic() + _CHAMPION_IMAGE_CACHE_TTL,
        }
    return profile


def _fetch_champion_image(character_name):
    """기존 호출부 호환성을 유지하는 캐릭터 이미지 조회 함수."""
    return _fetch_champion_profile(character_name).get("character_image")


def _enrich_champion_images(source):
    """유니온 챔피언 카드에 공식 이미지와 공개 캐릭터 정보를 보강한다."""
    current = source.get("currentData") or {}
    champions = current.get("union_champion")
    if not isinstance(champions, list) or not champions:
        return source

    missing = [
        champion for champion in champions
        if isinstance(champion, dict)
        and champion.get("champion_name")
        and any(not champion.get(field) for field in (
            "character_image", "character_level", "character_class"
        ))
    ]
    if not missing:
        return source

    with ThreadPoolExecutor(max_workers=min(3, len(missing))) as executor:
        profiles = list(executor.map(
            lambda champion: _fetch_champion_profile(champion.get("champion_name")),
            missing,
        ))
    for champion, profile in zip(missing, profiles):
        for field in (
            "character_image", "character_level",
            "character_class", "character_world_name"
        ):
            if not champion.get(field) and profile.get(field) is not None:
                champion[field] = profile[field]
    return source


def _fetch_source(ocid, spec, force_refresh=False):
    params = {"ocid": ocid, **spec.get("params", {})}
    cache_key = "nexon-source:{}:{}:{}:{}".format(
        ocid, spec["endpoint"], json.dumps(params, sort_keys=True, ensure_ascii=False),
        json.dumps(spec, sort_keys=True, ensure_ascii=False)
    )
    now = time.monotonic()
    if not force_refresh:
        with _SOURCE_CACHE_LOCK:
            cached_item = _SOURCE_CACHE.get(cache_key)
            if cached_item and cached_item["expires_at"] > now:
                return cached_item["source"]
            if cached_item:
                _SOURCE_CACHE.pop(cache_key, None)
    try:
        response = request_nexon_api(spec["endpoint"], params)
    except requests.RequestException:
        return {
            "id": spec["id"],
            "label": spec["label"],
            "status": "unavailable",
            "message": "넥슨 API 연결에 실패했습니다.",
        }

    if response.status_code != 200:
        return {
            "id": spec["id"],
            "label": spec["label"],
            "status": "unavailable",
            "statusCode": response.status_code,
            "message": (
                "요청이 일시적으로 제한되었습니다."
                if response.status_code == 429
                else "이 데이터는 현재 조회할 수 없습니다."
            ),
        }

    try:
        payload = response.json()
    except (ValueError, requests.RequestException):
        payload = None

    if not isinstance(payload, dict):
        payload = {}

    result = _normalize_source(payload, spec)
    source = {
        "id": spec["id"], "label": spec["label"], **result,
        "message": "API 응답에 표시할 데이터가 없습니다." if result["status"] == "empty" else None,
    }
    if spec["id"] == "unionChampion" and source["status"] == "available":
        source = _enrich_champion_images(source)
    with _SOURCE_CACHE_LOCK:
        _SOURCE_CACHE[cache_key] = {
            "source": source,
            "expires_at": time.monotonic() + _SOURCE_CACHE_TTL,
        }
    return source


def get_current_combat_power(ocid, force_refresh=False):
    """메인 프로필에서 실제 적용 중인 전투력을 조회한다.

    스탯 상세 탭과 같은 소스 캐시를 사용하므로, 메인 프로필 조회 직후
    상세 스탯 화면을 열어도 character/stat API를 중복 호출하지 않는다.
    """
    if not ocid:
        return None
    source = _fetch_source(
        ocid, SECTION_SOURCES["stats"][0], force_refresh=force_refresh
    )
    return source.get("combatPower") if source.get("status") == "available" else None


def get_character_detail_section(ocid, section, force_refresh=False):
    """선택된 상세 탭에 필요한 API만 병렬 조회한다."""
    if section not in VALID_SECTIONS:
        raise ValueError("지원하지 않는 상세 정보 구분입니다.")

    specs = SECTION_SOURCES[section]
    with ThreadPoolExecutor(max_workers=min(4, len(specs))) as executor:
        sources = list(executor.map(
            lambda spec: _fetch_source(ocid, spec, force_refresh=force_refresh),
            specs,
        ))

    available = sum(source["status"] == "available" for source in sources)
    if available == len(sources):
        status = "available"
    elif available:
        status = "partial"
    elif any(source["status"] == "empty" for source in sources):
        status = "partial"
    else:
        status = "unavailable"

    return {
        "section": section,
        "status": status,
        "sources": sources,
    }
