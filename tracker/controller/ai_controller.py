"""AI 성장 분석 HTTP 라우트."""
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from tracker.services.nexon_service import resolve_character, is_temporary_nexon_failure
from tracker.services.request_limits import consume_ai_request
from tracker.domain.ai_growth_insights import build_growth_insights
from tracker.runtime import KOREA_TIMEZONE, get_growth_history_service
from tracker.services.ai_analysis_service import (
    generate_ai_analysis,
    generate_ai_comparison,
)

ai_bp = Blueprint("ai", __name__, url_prefix="/api")


def _ai_rate_limit_response():
    allowed, retry_after, reason = consume_ai_request(request.remote_addr)
    if allowed:
        return None
    response = jsonify({
        "error": "AI 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
        "limitType": reason,
        "retryAfter": retry_after,
    })
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


@ai_bp.route("/ai-analysis", methods=["GET", "POST"])
def ai_analysis():
    """캐릭터의 계산된 성장 지표를 바탕으로 AI 성장 리포트를 만든다."""
    character_name = request.args.get("name", "").strip()
    if not character_name:
        return jsonify({"error": "캐릭터명을 입력해주세요."}), 400
    if len(character_name) > 30:
        return jsonify({"error": "캐릭터 이름이 너무 깁니다."}), 400
    metrics = None
    supplied_history = None
    analysis_context = {}
    force_refresh = False
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        metrics = payload.get("metrics")
        supplied_history = payload.get("history")
        force_refresh = payload.get("forceRefresh", False)
        if not isinstance(force_refresh, bool):
            return jsonify({"error": "재분석 요청 값이 올바르지 않습니다."}), 400
        raw_context = payload.get("analysisContext")
        if raw_context is not None and not isinstance(raw_context, dict):
            return jsonify({"error": "분석 기간 정보 형식이 올바르지 않습니다."}), 400
        raw_context = raw_context or {}
        period_days = raw_context.get("periodDays", 7)
        if isinstance(period_days, bool) or period_days not in (7, 30, 90):
            return jsonify({"error": "분석 기간은 7일, 30일, 90일 중 하나여야 합니다."}), 400
        period_summary = raw_context.get("periodSummary")
        if period_summary is not None and not isinstance(period_summary, dict):
            return jsonify({"error": "기간별 분석 근거 형식이 올바르지 않습니다."}), 400
        analysis_context = {"periodDays": period_days, "periodSummary": period_summary}
        if not isinstance(metrics, dict):
            return jsonify({"error": "계산된 성장 지표가 필요합니다."}), 400
        if supplied_history is not None and not isinstance(supplied_history, list):
            return jsonify({"error": "성장 기록 형식이 올바르지 않습니다."}), 400
        supplied_history = [
            {
                key: item.get(key)
                for key in (
                    "date", "level", "experience", "experienceChange", "ranking",
                    "rankingChange", "levelUp", "recordStatus"
                )
                if key in item
            }
            for item in (supplied_history or [])[:90]
            if isinstance(item, dict) and item.get("date")
        ]
    rate_limit_response = _ai_rate_limit_response()
    if rate_limit_response:
        return rate_limit_response

    try:
        # AI 분석은 랭킹 API에 의존하지 않는다. 기본 캐릭터 정보만 확인해
        # 랭킹 조회 장애가 성장 분석 전체를 막지 않도록 분리한다.
        ocid, basic, basic_response = resolve_character(character_name)
        if not ocid or not basic:
            status = 503 if is_temporary_nexon_failure(basic_response) else 404
            return jsonify({"error": "캐릭터 기본 정보를 확인하지 못했습니다."}), status
        character = {
            "characterName": basic.get("character_name"),
            "worldName": basic.get("world_name"),
            "job": basic.get("character_class"),
            "level": basic.get("character_level"),
            "experience": basic.get("character_exp"),
            "experienceRate": basic.get("character_exp_rate"),
            "ocid": ocid,
        }

        if supplied_history is not None:
            recent_history = supplied_history
        else:
            # GET 호환 및 기존 클라이언트용 fallback
            from tracker.controller.history_controller import get_history
            history_response = get_history()
            if history_response.status_code != 200:
                return jsonify({"error": "성장 기록을 불러오지 못했습니다."}), history_response.status_code
            history_data = history_response.get_json()
            recent_history = history_data.get("history", [])
        today = datetime.now(KOREA_TIMEZONE).date()
        # A client-side cache or malformed payload must not make future
        # snapshots appear as already-observed growth in the AI report.
        observed_history = []
        for item in recent_history:
            try:
                record_date = date.fromisoformat(str(item.get("date", "")))
            except (TypeError, ValueError, AttributeError):
                continue
            if record_date <= today:
                observed_history.append(item)
        recent_history = observed_history
        insight_records = list(recent_history)

        # 30일·90일 화면에서 저장한 과거 기록이 있으면 읽기만 한다.
        # 이 과정에서는 Nexon API를 추가 호출하거나 누락 날짜를 보정하지 않는다.
        ocid = character.get("ocid")
        if ocid:
            try:
                stored_records = get_growth_history_service().get_records(
                    ocid, today - timedelta(days=14), today
                )
                records_by_date = {
                    item.get("date"): item
                    for item in stored_records
                    if item.get("date")
                }
                for item in recent_history:
                    if item.get("date"):
                        existing = records_by_date.get(item["date"])
                        if existing is None or item.get("recordStatus") == "available":
                            records_by_date[item["date"]] = item
                insight_records = list(records_by_date.values())
            except Exception:
                # 저장소 상태가 AI 기본 분석을 막지 않도록 최근 응답으로 계산한다.
                print("AI 분석용 장기 성장 기록을 조회하지 못했습니다.")

        growth_insights = build_growth_insights(
            insight_records, reference_date=today
        )
        result = generate_ai_analysis(
            character, recent_history, metrics, growth_insights, analysis_context, force_refresh
        )
        if "error" in result:
            return jsonify(result), 500
        return jsonify(result)
    except Exception as error:
        print(f"Gemini AI 분석 API 요청에 실패했습니다: {error}")
        return {"error": "AI 분석을 불러오지 못했습니다."}

@ai_bp.route("/ai-comparison", methods=["POST"])
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

    rate_limit_response = _ai_rate_limit_response()
    if rate_limit_response:
        return rate_limit_response

    result = generate_ai_comparison(primary, comparison)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)
