"""Nexon Open API 캐릭터 상세 데이터 조회 및 프리셋 정규화."""
from concurrent.futures import ThreadPoolExecutor

import requests

from tracker.integrations.nexon_api import request_nexon_api


SECTION_SOURCES = {
    "stats": [
        {"id": "stat", "label": "주요 스탯", "endpoint": "character/stat"},
        {
            "id": "hyperStat",
            "label": "하이퍼 스탯",
            "endpoint": "character/hyper-stat",
            "preset_prefix": "hyper_stat_preset_",
            "active_fields": ("use_preset_no",),
            "current_fields": ("hyper_stat",),
            "preset_count": 3,
        },
        {
            "id": "ability",
            "label": "어빌리티",
            "endpoint": "character/ability",
            "preset_prefix": "ability_preset_",
            "active_fields": ("ability_preset_no", "use_preset_no"),
            "current_fields": ("ability_info",),
            "preset_count": 3,
        },
    ],
    "equipment": [
        {
            "id": "itemEquipment",
            "label": "장비",
            "endpoint": "character/item-equipment",
            "preset_prefix": "item_equipment_preset_",
            "active_fields": ("preset_no",),
            "current_fields": ("item_equipment",),
            "preset_count": 3,
        },
        {
            "id": "symbolEquipment",
            "label": "아케인·어센틱 심볼",
            "endpoint": "character/symbol-equipment",
            "current_fields": ("symbol",),
        },
        {
            "id": "setEffect",
            "label": "세트 효과",
            "endpoint": "character/set-effect",
            "current_fields": ("set_effect",),
        },
    ],
    "link": [
        {
            "id": "linkSkill",
            "label": "링크 스킬",
            "endpoint": "character/link-skill",
            "preset_prefix": "character_link_skill_preset_",
            "active_fields": ("use_preset_no", "character_link_skill_preset_no"),
            "current_fields": ("character_link_skill",),
            "preset_count": 3,
        },
    ],
    "union": [
        {
            "id": "union",
            "label": "유니온 기본 정보",
            "endpoint": "user/union",
        },
        {
            "id": "unionRaider",
            "label": "유니온 공격대",
            "endpoint": "user/union-raider",
            "preset_groups": ("union_raider_preset_", "union_block_preset_"),
            "active_fields": ("union_raider_preset_no", "union_block_preset_no"),
            "preset_count": 5,
        },
        {
            "id": "unionArtifact",
            "label": "유니온 아티팩트",
            "endpoint": "user/union-artifact",
            "preset_prefix": "union_artifact_preset_",
            "active_fields": ("union_artifact_preset_no",),
            "preset_count": 3,
        },
    ],
}

VALID_SECTIONS = frozenset(SECTION_SOURCES)


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


def _normalize_source(payload, spec):
    """API 원본은 유지하되 프리셋 목록과 현재 선택 번호를 별도로 추출한다."""
    payload = payload if isinstance(payload, dict) else {}
    prefixes = []
    preset_groups = spec.get("preset_groups")
    if preset_groups:
        prefixes.extend(preset_groups)
    if spec.get("preset_prefix"):
        prefixes.append(spec["preset_prefix"])

    presets = []
    count = int(spec.get("preset_count", 0))
    for number in range(1, count + 1):
        selected = {}
        for prefix in prefixes:
            field = f"{prefix}{number}"
            value = payload.get(field)
            if _has_data(value):
                selected[field] = value
        if selected:
            presets.append({"number": number, "data": selected})

    current_fields = spec.get("current_fields", ())
    current_data = {
        field: payload[field]
        for field in current_fields
        if _has_data(payload.get(field))
    }

    # API 버전이나 캐릭터 상태에 따라 프리셋 배열이 비어 있을 수 있다.
    # 이 경우 현재 구성만 제공하고, 존재하지 않는 프리셋은 만들어내지 않는다.
    if not presets and current_data:
        presets = [{"number": 0, "data": current_data, "currentOnly": True}]

    excluded = set(current_fields)
    excluded.update(spec.get("active_fields", ()))
    for prefix in prefixes:
        excluded.update(key for key in payload if key.startswith(prefix))

    data = {
        key: value for key, value in payload.items()
        if key not in excluded and not key.startswith("preset_")
    }
    active = _active_preset(payload, spec.get("active_fields", ()))

    # 주요 스탯은 현재 적용 상태에서 API가 반환한 값만 전투력으로 표시한다.
    combat_power = None
    final_stats = payload.get("final_stat")
    if isinstance(final_stats, list):
        for item in final_stats:
            if not isinstance(item, dict):
                continue
            name = str(item.get("stat_name", "")).strip()
            if name == "전투력":
                combat_power = item.get("stat_value")
                break

    return {
        "status": "available" if data or presets else "empty",
        "activePresetNo": active,
        "presets": presets,
        "data": data,
        "combatPower": combat_power,
    }


def _fetch_source(ocid, spec):
    try:
        response = request_nexon_api(spec["endpoint"], {"ocid": ocid})
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
    return {
        "id": spec["id"],
        "label": spec["label"],
        **result,
        "message": (
            "API 응답에 표시할 데이터가 없습니다."
            if result["status"] == "empty"
            else None
        ),
    }


def get_character_detail_section(ocid, section):
    """선택된 상세 탭에 필요한 API만 병렬 조회한다."""
    if section not in VALID_SECTIONS:
        raise ValueError("지원하지 않는 상세 정보 구분입니다.")

    specs = SECTION_SOURCES[section]
    with ThreadPoolExecutor(max_workers=min(3, len(specs))) as executor:
        sources = list(executor.map(
            lambda spec: _fetch_source(ocid, spec),
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
