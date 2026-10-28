"""Flask HTTP 컨트롤러."""

from app import *


@app.route("/api/ai-analysis", methods=["GET", "POST"])
def ai_analysis():
    """캐릭터의 계산된 성장 지표를 바탕으로 AI 성장 리포트를 만든다."""
    character_name = request.args.get("name", "").strip()
    if not character_name:
        return jsonify({"error": "캐릭터명을 입력해주세요."}), 400

    try:
        character_response = get_character()
        if character_response.status_code != 200:
            return jsonify({"error": "캐릭터 정보를 불러오지 못했습니다."}), character_response.status_code
        character = character_response.get_json()
        request.environ["maple_character_context"] = character

        history_response = get_history()
        if history_response.status_code != 200:
            return jsonify({"error": "성장 기록을 불러오지 못했습니다."}), history_response.status_code
        history_data = history_response.get_json()
        metrics = None
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            metrics = payload.get("metrics")
            if not isinstance(metrics, dict):
                return jsonify({"error": "계산된 성장 지표가 필요합니다."}), 400

        result = generate_ai_analysis(character, history_data.get("history", []), metrics)
        if "error" in result:
            return jsonify(result), 500
        return jsonify(result)
    except Exception as error:
        print(f"Gemini AI 분석 API 요청에 실패했습니다: {error}")
        return {"error": "AI 분석을 불러오지 못했습니다."}

@app.route("/api/ai-comparison", methods=["POST"])
def ai_comparison():
    """두 캐릭터의 계산된 성장 지표를 바탕으로 비교 설명을 만든다."""
    payload = request.get_json(silent=True) or {}
    primary = payload.get("primary")
    comparison = payload.get("comparison")
    if not isinstance(primary, dict) or not isinstance(comparison, dict):
        return jsonify({"error": "두 캐릭터의 성장 데이터가 필요합니다."}), 400

    for subject in (primary, comparison):
        if not isinstance(subject.get("character"), dict) or not isinstance(subject.get("metrics"), dict):
            return jsonify({"error": "캐릭터 정보와 계산된 성장 지표가 필요합니다."}), 400
        if not subject["character"].get("characterName"):
            return jsonify({"error": "캐릭터명을 확인할 수 없습니다."}), 400

    first_name = primary["character"]["characterName"].strip().casefold()
    second_name = comparison["character"]["characterName"].strip().casefold()
    if first_name == second_name:
        return jsonify({"error": "같은 캐릭터는 비교할 수 없습니다."}), 400

    result = generate_ai_comparison(primary, comparison)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)
