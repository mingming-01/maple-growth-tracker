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
         "preset_prefix": "ability_preset_", "active_fields": ("ability_preset_no", "use_preset_no"),
         "current_fields": ("ability_info",), "preset_count": 3},
        {"id": "itemEquipment", "label": "장비 프리셋", "endpoint": "character/item-equipment",
         "preset_prefix": "item_equipment_preset_", "active_fields": ("preset_no",),
         "current_fields": ("item_equipment",), "preset_count": 3},
        {"id": "linkSkill", "label": "링크 스킬 프리셋", "endpoint": "character/link-skill",
         "preset_groups": ("character_link_skill_preset_", "character_owned_link_skill_preset_"),
         "active_fields": ("use_preset_no", "character_link_skill_preset_no"),
         "current_fields": ("character_link_skill", "character_owned_link_skill"), "preset_count": 3},
        {"id": "unionStateStat", "label": "유니온 스탯", "endpoint": "user/union-raider",
         "preset_list_field": "union_state_stat_preset",
         "preset_number_field": "preset_no",
         "preset_data_field": "union_state_stat",
         "current_fields": ("union_state_stat",),
         "exclude_fields": ("union_raider_stat", "union_occupied_stat", "union_inner_stat",
                            "union_block", "use_preset_no")},

    ],
    "equipment": [
        {"id": "itemEquipment", "label": "장비", "endpoint": "character/item-equipment",
         "preset_prefix": "item_equipment_preset_", "active_fields": ("preset_no",),
         "current_fields": ("item_equipment",), "preset_count": 3},
        {"id": "setEffect", "label": "세트 효과", "endpoint": "character/set-effect",
         "current_fields": ("set_effect",)},
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
    "hyper_stat_preset_": "hyper_stat",
    "ability_preset_": "ability_info",
    "character_link_skill_preset_": "character_link_skill",
    "character_owned_link_skill_preset_": "character_owned_link_skill",

}
_SOURCE_CATEGORY = {
    "itemEquipment": "equipment",
    "hyperStat": "hyperStat",
    "ability": "ability",
    "linkSkill": "link",
    "unionStateStat": "union",
}


def _flatten_text(value):
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text(item) for item in value)
    return str(value) if value is not None else ""


def _classify_preset(source_id, value):
    """장비·링크·하이퍼·어빌리티·유니온별 실제 옵션 신호를 점수화한다."""
    text = _flatten_text(value).lower()
    boss = 0
    hunting = 0
    signals = []

    if source_id == "itemEquipment":
        rings = (
            "리스트레인트 링", "컨티뉴어스 링", "웨폰퍼프 링",
            "리스크테이커 링", "크라이시스 링", "레벨퍼프 링", "얼티메이덤 링",
        )
        matched = [name for name in rings if name in text]
        if matched:
            boss += 4
            signals.extend(matched)
        if "메소 획득량" in text:
            hunting += 4
            signals.append("메소 획득량")
        if "아이템 드롭률" in text or "드롭률" in text:
            hunting += 4
            signals.append("아이템 드롭률")
        # 드랍/메획이 없다는 이유만으로 보스 프리셋이라 단정하지 않는다.
        if matched and "메소 획득량" not in text and "드롭률" not in text:
            boss += 1

    elif source_id == "linkSkill":
        for name in ("소울 컨트랙트", "데몬스 퓨리"):
            if name in text:
                boss += 3
                signals.append(name)
        for name in ("엘프의 축복", "룬 퍼시스턴스", "콤보킬 어드밴티지"):
            if name in text:
                hunting += 3
                signals.append(name)

    elif source_id == "hyperStat":
        for name, weight in (
            ("보스 몬스터 공격 시 데미지", 3), ("보스 데미지", 3),
            ("방어율 무시", 2), ("크리티컬 데미지", 2),
            ("공격력", 1), ("마력", 1),
        ):
            if name in text:
                boss += weight
                signals.append(name)
        for name, weight in (
            ("메소 획득량", 4), ("아이템 드롭률", 4), ("드롭률", 4),
            ("일반 몬스터", 3), ("경험치 획득량", 3),
        ):
            if name in text:
                hunting += weight
                signals.append(name)

    elif source_id == "ability":
        for name, weight in (
            ("보스 몬스터 공격 시 데미지", 3), ("보스 데미지", 3),
            ("공격력", 1), ("마력", 1), ("재사용 대기시간 미적용", 2),
        ):
            if name in text:
                boss += weight
                signals.append(name)
        for name, weight in (
            ("메소 획득량", 4), ("아이템 드롭률", 4), ("드롭률", 4),
            ("일반 몬스터", 2),
        ):
            if name in text:
                hunting += weight
                signals.append(name)

    elif source_id == "unionStateStat":
        for name in ("보스 몬스터 공격 시 데미지", "보스 데미지", "방어율 무시",
                     "크리티컬 데미지", "최종 데미지"):
            if name in text:
                boss += 2
                signals.append(name)
        for name in ("일반 몬스터 공격 시 데미지", "경험치 획득량",
                     "메소 획득량", "아이템 드롭률"):
            if name in text:
                hunting += 2
                signals.append(name)

    purpose = "unknown"
    if boss >= 2 and boss > hunting:
        purpose = "boss"
    elif hunting >= 2 and hunting > boss:
        purpose = "hunting"
    return {
        "purpose": purpose,
        "bossScore": boss,
        "huntingScore": hunting,
        "signals": list(dict.fromkeys(signals)),
    }


def _recommend_profile(sources, purpose):
    selected = {}
    matched = []
    total_score = 0
    score_key = "bossScore" if purpose == "boss" else "huntingScore"

    for source in sources:
        category = _SOURCE_CATEGORY.get(source.get("id"))
        presets = source.get("presets") or []
        if not category or not presets:
            continue
        ranked = sorted(presets, key=lambda item: int(item.get(score_key, 0) or 0), reverse=True)
        best = ranked[0]
        score = int(best.get(score_key, 0) or 0)
        if score >= 2:
            selected[category] = best["number"]
            matched.append(category)
            total_score += score
        else:
            active = next(
                (item for item in presets if item.get("number") == source.get("activePresetNo")),
                None,
            )
            selected[category] = (active or presets[0])["number"]

    confidence = "high" if len(matched) >= 3 and total_score >= 9 else "medium" if matched else "low"
    return {
        "presetNumbers": selected,
        "matchedCategories": matched,
        "score": total_score,
        "confidence": confidence,
    }


def recommend_preset_profiles(sources):
    """여러 데이터 영역의 신호를 합쳐 보스·사냥 세팅 조합을 추천한다."""
    return {
        "boss": _recommend_profile(sources, "boss"),
        "hunting": _recommend_profile(sources, "hunting"),
    }


def _preset_data_key(prefix):
    return _PRESET_DATA_KEYS.get(prefix, prefix.rstrip("_"))


def _normalize_source(payload, spec):
    """Nexon 원본 응답을 화면에서 사용하는 공통 데이터 구조로 정규화한다."""
    payload = payload if isinstance(payload, dict) else {}

    # 최신 KMS 유니온 스탯은 preset_1 같은 개별 필드가 아니라
    # union_state_stat_preset 배열 안에 preset_no와 효과 목록으로 제공된다.
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
                presets.append({
                    "number": number,
                    "data": selected,
                    **_classify_preset(spec["id"], selected),
                })

        current_fields = spec.get("current_fields", ())
        current_data = {
            field: payload[field]
            for field in current_fields
            if _has_data(payload.get(field))
        }
        # 현 적용 프리셋 번호는 별도 필드로 오지 않을 수 있다.
        # 현재 효과 목록과 프리셋 효과 목록이 완전히 일치할 때만 활성 번호를 확정한다.
        active_number = None
        current_values = current_data.get(value_field)
        if isinstance(current_values, list):
            current_signature = json.dumps(sorted(str(value) for value in current_values), ensure_ascii=False, separators=(",", ":"))
            for preset in presets:
                preset_values = preset["data"].get(value_field, [])
                preset_signature = json.dumps(sorted(str(value) for value in preset_values), ensure_ascii=False, separators=(",", ":"))
                if current_signature == preset_signature:
                    active_number = preset["number"]
                    break

        excluded = set(current_fields) | {preset_list_field} | set(spec.get("exclude_fields", ()))
        data = {
            key: value
            for key, value in payload.items()
            if key not in excluded
        }
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
                selected[_preset_data_key(prefix)] = value
        if selected:
            presets.append({
                "number": number,
                "data": selected,
                **_classify_preset(spec["id"], selected),
            })

    current_fields = spec.get("current_fields", ())
    current_data = {
        field: payload[field]
        for field in current_fields
        if _has_data(payload.get(field))
    }
    if not presets and current_data:
        presets = [{
            "number": 0,
            "data": current_data,
            "currentOnly": True,
            **_classify_preset(spec["id"], current_data),
        }]

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




def _fetch_source(ocid, spec, force_refresh=False):
    params = {"ocid": ocid, **spec.get("params", {})}
    cache_key = "nexon-source:{}:{}:{}".format(
        ocid, spec["endpoint"], json.dumps(params, sort_keys=True, ensure_ascii=False)
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
    with _SOURCE_CACHE_LOCK:
        _SOURCE_CACHE[cache_key] = {
            "source": source,
            "expires_at": time.monotonic() + _SOURCE_CACHE_TTL,
        }
    return source


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
