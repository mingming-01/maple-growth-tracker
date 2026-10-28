"""Flask HTTP 컨트롤러."""

from app import *


@app.route("/api/character")
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

    try:
        ocid, response = get_ocid(character_name)
        if not ocid:
            if is_temporary_nexon_failure(response):
                return stale_snapshot_response(
                    cache_key, "넥슨 API가 일시적으로 응답하지 않습니다. 잠시 후 다시 시도해주세요."
                )
            return jsonify({"error": "캐릭터 정보를 찾을 수 없거나 조회할 수 없습니다."}), response.status_code

        basic, response = get_basic_character(ocid)
        if not basic:
            if is_temporary_nexon_failure(response):
                return stale_snapshot_response(
                    cache_key, "캐릭터 정보를 일시적으로 조회할 수 없습니다. 잠시 후 다시 시도해주세요."
                )
            return jsonify({"error": "캐릭터 정보를 확인할 수 없습니다."}), response.status_code

        character_class = basic["character_class"]
        character_rankings = get_character_rankings(
            target_date=datetime.now(KOREA_TIMEZONE).strftime("%Y-%m-%d"),
            world_name=basic["world_name"],
            character_class=character_class,
            ocid=ocid
        )
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
        "rankingDataStatus": character_rankings["rankingDataStatus"]
    }

    data_status = "partial" if character_rankings["rankingDataStatus"] in ("partial", "unavailable") else "current"
    saved_at = datetime.now().astimezone().isoformat(timespec="seconds")

    # 일시적으로 빈 응답이 와도 기존의 정상 랭킹 스냅샷은 덮어쓰지 않는다.
    previous_snapshot, _ = load_api_snapshot(cache_key)
    if character_rankings["rankingDataStatus"] == "available" or previous_snapshot is None:
        snapshot_saved_at = save_api_snapshot(cache_key, result)
        if snapshot_saved_at:
            saved_at = snapshot_saved_at

    set_cache(cache_key, result, CHARACTER_CACHE_TTL)
    return jsonify(with_data_status(result, data_status, saved_at))
