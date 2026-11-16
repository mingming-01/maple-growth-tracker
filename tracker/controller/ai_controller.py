"""AI 성장 분석 HTTP 라우트."""
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from tracker.services.nexon_service import resolve_character, is_temporary_nexon_failure
from tracker.services.request_limits import consume_ai_request
from tracker.domain.ai_growth_insights import build_growth_insights
from tracker.domain.ai_metrics import build_server_growth_metrics
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


def _service_error_response(result):
    """서비스 계층의 공급자 상태를 HTTP 응답에 정확히 반영한다."""
    payload = dict(result)
    status_code = payload.pop("statusCode", 502)
    retry_after = payload.get("retryAfterSeconds")
    response = jsonify(payload)
    response.status_code = status_code if isinstance(status_code, int) and 400 <= status_code <= 599 else 502
    if isinstance(retry_after, int) and retry_after > 0:
        response.headers["Retry-After"] = str(retry_after)
    return response


@ai_bp.route("/ai-analysis", methods=["GET", "POST"])
def ai_analysis():
    """저장된 성장 기록으로 지표를 재계산해 AI 성장 리포트를 만든다."""
    character_name = request.args.get("name", "").strip()
    if not character_name:
        return jsonify({"error": "캐릭터명을 입력해주세요."}), 400
    if len(character_name) > 30:
        return jsonify({"error": "캐릭터 이름이 너무 깁니다."}), 400

    period_days = 7
    force_refresh = False
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "분석 요청 형식이 올바르지 않습니다."}), 400
        force_refresh = payload.get("forceRefresh", False)
        if not isinstance(force_refresh, bool):
            return jsonify({"error": "재분석 요청 값이 올바르지 않습니다."}), 400
        raw_context = payload.get("analysisContext")
        if raw_context is not None and not isinstance(raw_context, dict):
            return jsonify({"error": "분석 기간 정보 형식이 올바르지 않습니다."}), 400
        period_days = (raw_context or {}).get("periodDays", 7)
        if isinstance(period_days, bool) or period_days not in (7, 30, 90):
            return jsonify({"error": "분석 기간은 7일, 30일, 90일 중 하나여야 합니다."}), 400

    rate_limit_response = _ai_rate_limit_response()
    if rate_limit_response:
        return rate_limit_response

    try:
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

        today = datetime.now(KOREA_TIMEZONE).date()
        storage = get_growth_history_service()
        try:
            stored_records = storage.get_records(
                ocid, today - timedelta(days=period_days - 1), today
            )
            insight_records = storage.get_records(
                ocid, today - timedelta(days=14), today
            )
        except Exception:
            return jsonify({"error": "서버에 저장된 성장 기록을 확인할 수 없습니다."}), 503

        calculated = build_server_growth_metrics(
            character, stored_records, reference_date=today, period_days=period_days
        )
        recent_history = calculated["history"]
        analysis_context = {
            "periodDays": period_days,
            "periodSummary": calculated["periodSummary"],
        }
        growth_insights = build_growth_insights(insight_records, reference_date=today)
        result = generate_ai_analysis(
            character,
            recent_history,
            calculated["metrics"],
            growth_insights,
            analysis_context,
            force_refresh,
        )
        if "error" in result:
            return _service_error_response(result)
        return jsonify(result)
    except Exception as error:
        print(f"AI 분석 API 요청에 실패했습니다: {error}")
        return jsonify({"error": "AI 분석을 불러오지 못했습니다."}), 502


@ai_bp.route("/ai-comparison", methods=["POST"])
def ai_comparison():
    """두 캐릭터의 저장된 성장 기록을 서버에서 재계산해 비교한다."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "두 캐릭터의 성장 데이터가 필요합니다."}), 400
    primary_payload = payload.get("primary")
    comparison_payload = payload.get("comparison")
    if not isinstance(primary_payload, dict) or not isinstance(comparison_payload, dict):
        return jsonify({"error": "두 캐릭터의 성장 데이터가 필요합니다."}), 400

    subjects = []
    for subject in (primary_payload, comparison_payload):
        character_payload = subject.get("character")
        if not isinstance(character_payload, dict):
            return jsonify({"error": "캐릭터 정보를 확인할 수 없습니다."}), 400
        name = character_payload.get("characterName")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 30:
            return jsonify({"error": "캐릭터명을 확인할 수 없습니다."}), 400
        subjects.append(name.strip())

    if subjects[0].casefold() == subjects[1].casefold():
        return jsonify({"error": "같은 캐릭터는 비교할 수 없습니다."}), 400

    rate_limit_response = _ai_rate_limit_response()
    if rate_limit_response:
        return rate_limit_response

    try:
        today = datetime.now(KOREA_TIMEZONE).date()
        storage = get_growth_history_service()
        prepared = []
        for name in subjects:
            ocid, basic, basic_response = resolve_character(name)
            if not ocid or not basic:
                status = 503 if is_temporary_nexon_failure(basic_response) else 404
                return jsonify({"error": f"{name} 캐릭터 정보를 확인하지 못했습니다."}), status
            character = {
                "characterName": basic.get("character_name"),
                "worldName": basic.get("world_name"),
                "job": basic.get("character_class"),
                "level": basic.get("character_level"),
                "experience": basic.get("character_exp"),
                "experienceRate": basic.get("character_exp_rate"),
                "ocid": ocid,
            }
            records = storage.get_records(ocid, today - timedelta(days=89), today)
            calculated = build_server_growth_metrics(
                character, records, reference_date=today, period_days=90
            )
            prepared.append({
                "character": character,
                "metrics": calculated["metrics"],
                "history": calculated["history"],
            })

        result = generate_ai_comparison(prepared[0], prepared[1])
        if "error" in result:
            return _service_error_response(result)
        return jsonify(result)
    except Exception as error:
        print(f"AI 비교 API 요청에 실패했습니다: {error}")
        return jsonify({"error": "AI 성장 비교를 불러오지 못했습니다."}), 502
