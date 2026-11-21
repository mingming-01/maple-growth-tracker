"""AI 성장 분석 HTTP 라우트."""
from datetime import date, datetime, timedelta
import time

from flask import Blueprint, current_app, jsonify, request

from tracker.services.nexon_service import resolve_character, is_temporary_nexon_failure
from tracker.services.request_limits import consume_ai_request
from tracker.domain.ai_growth_insights import build_growth_insights
from tracker.domain.ai_metrics import build_server_growth_metrics
from tracker.runtime import KOREA_TIMEZONE, get_growth_history_service, load_api_snapshot
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
    """일반 응답에는 사용자용 오류 문구만 남기고 진단 정보는 서버 로그에 둔다."""
    status_code = result.get("statusCode", 502)
    retry_after = result.get("retryAfterSeconds")
    error_message = result.get("error") or "AI 분석을 처리하지 못했습니다."
    response = jsonify({"error": str(error_message)})
    response.status_code = status_code if isinstance(status_code, int) and 400 <= status_code <= 599 else 502
    if isinstance(retry_after, int) and retry_after > 0:
        response.headers["Retry-After"] = str(retry_after)
    return response


def _public_ai_analysis_payload(result):
    """일반 사용자 응답에는 분석 결과와 간단한 폴백 여부만 전달한다."""
    payload = dict(result)
    generation = payload.pop("generation", None)
    payload.pop("providerMetadata", None)
    payload.pop("delivery", None)
    payload.pop("aiFallbackReason", None)
    payload.pop("aiStatus", None)
    payload["aiFallbackUsed"] = (
        isinstance(generation, dict) and generation.get("fallbackUsed") is True
    )
    return payload


def _resolve_character_for_ai(character_name):
    """AI 엔드포인트의 Nexon 조회는 짧은 1회 요청으로 제한한다."""
    timeout = (
        float(current_app.config.get("AI_NEXON_CONNECT_TIMEOUT", 1.5)),
        float(current_app.config.get("AI_NEXON_READ_TIMEOUT", 2.5)),
    )
    return resolve_character(
        character_name,
        timeout_override=timeout,
        max_attempts_override=1,
    )


AI_CHARACTER_SNAPSHOT_MAX_AGE_SECONDS = 5 * 60


def _load_recent_character_profile(character_name, now=None):
    """최근 캐릭터 화면 조회가 저장한 프로필을 재사용해 Nexon 재조회 시간을 줄인다."""
    try:
        snapshot, saved_at = load_api_snapshot(f"character:{character_name}")
        if not isinstance(snapshot, dict) or not saved_at:
            return None
        saved_name = str(snapshot.get("characterName") or "").strip()
        world_name = str(snapshot.get("worldName") or "").strip()
        ocid = str(snapshot.get("ocid") or "").strip()
        if (
            not saved_name
            or saved_name.casefold() != character_name.casefold()
            or not world_name
            or not ocid
            or snapshot.get("level") is None
        ):
            return None

        saved_time = datetime.fromisoformat(str(saved_at))
        current_time = now or datetime.now().astimezone()
        if saved_time.tzinfo is None:
            saved_time = saved_time.astimezone()
        age_seconds = (current_time - saved_time).total_seconds()
        if age_seconds < 0 or age_seconds > AI_CHARACTER_SNAPSHOT_MAX_AGE_SECONDS:
            return None

        return ocid, {
            "characterName": saved_name,
            "worldName": world_name,
            "job": snapshot.get("job"),
            "level": snapshot.get("level"),
            "experience": snapshot.get("experience"),
            "experienceRate": snapshot.get("experienceRate"),
            "ocid": ocid,
        }
    except Exception:
        # 캐시 저장소가 일시적으로 unavailable이어도 원래 Nexon 조회 경로로 폴백한다.
        return None


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

    request_started = time.perf_counter()
    stage_started = request_started
    stage = "profile"
    timings = {}

    try:
        cached_profile = _load_recent_character_profile(character_name)
        if cached_profile:
            ocid, character = cached_profile
        else:
            ocid, basic, basic_response = _resolve_character_for_ai(character_name)
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

        timings["profile_ms"] = round((time.perf_counter() - stage_started) * 1000, 1)
        stage = "history_db"
        stage_started = time.perf_counter()
        today = datetime.now(KOREA_TIMEZONE).date()
        storage = get_growth_history_service()
        period_start = today - timedelta(days=period_days - 1)
        insight_start = today - timedelta(days=14)
        previous_period_end = period_start - timedelta(days=1)
        previous_period_start = previous_period_end - timedelta(days=period_days - 1)
        # 장기 분석은 직전 동일 기간과 첫날 경계 계산에 필요한 스냅샷도
        # 서버 저장소에서 직접 조회한다. 클라이언트가 전달한 요약값은 신뢰하지 않는다.
        comparison_start = (
            previous_period_start - timedelta(days=1)
            if period_days in (30, 90)
            else period_start - timedelta(days=1)
        )
        query_start = min(comparison_start, insight_start)
        try:
            # 선택 기간과 14일 인사이트를 하나의 DB 조회로 확보한다.
            combined_records = storage.get_records(ocid, query_start, today)
        except Exception:
            current_app.logger.exception(
                "AI 리포트 요청 중 저장 기록 조회 실패: period_days=%s", period_days
            )
            return jsonify({"error": "서버에 저장된 성장 기록을 확인할 수 없습니다."}), 503

        timings["history_db_ms"] = round((time.perf_counter() - stage_started) * 1000, 1)
        stage = "calculation"
        stage_started = time.perf_counter()
        # 하나의 원본 구간을 공통 백엔드 계산기로 정규화한다.
        # 최근 성장 이력, 기간 통계, AI 비교 인사이트는 모두 이 결과에서 파생한다.
        calculation_start = period_start - timedelta(days=1)
        calculated = build_server_growth_metrics(
            character, combined_records, reference_date=today, period_days=period_days
        )
        normalized_history = calculated["history"]
        recent_history = [
            item for item in normalized_history
            if str(item.get("date") or "") >= calculation_start.isoformat()
        ]
        previous_period_summary = None
        if period_days in (30, 90):
            previous_calculated = build_server_growth_metrics(
                character,
                combined_records,
                reference_date=previous_period_end,
                period_days=period_days,
            )
            previous_period_summary = previous_calculated["periodSummary"]

        analysis_context = {
            "periodDays": period_days,
            "periodSummary": calculated["periodSummary"],
            "previousPeriodSummary": previous_period_summary,
        }
        growth_insights = build_growth_insights(
            normalized_history,
            reference_date=today,
            already_calculated=True,
        )
        timings["calculation_ms"] = round((time.perf_counter() - stage_started) * 1000, 1)
        stage = "provider"
        stage_started = time.perf_counter()
        result = generate_ai_analysis(
            character,
            recent_history,
            calculated["metrics"],
            growth_insights,
            analysis_context,
            force_refresh,
        )
        timings["provider_ms"] = round((time.perf_counter() - stage_started) * 1000, 1)
        total_ms = round((time.perf_counter() - request_started) * 1000, 1)
        if "error" in result:
            current_app.logger.warning(
                "AI 리포트 공급자 실패: error_type=%s primary_error=%s fallback_error=%s timings=%s total_ms=%s",
                result.get("errorType", "unknown"),
                result.get("primaryErrorType", ""),
                result.get("fallbackErrorType", ""),
                timings,
                total_ms,
            )
            return _service_error_response(result)

        # 화면의 기간 요약과 AI 리포트 본문이 동일한 서버 집계값을 사용하도록 반환한다.
        result["periodSummary"] = calculated["periodSummary"]
        result["previousPeriodSummary"] = previous_period_summary

        current_app.logger.info(
            "AI 리포트 응답 완료: ai_generated=%s ai_status=%s cache_hit=%s timings=%s total_ms=%s",
            result.get("aiGenerated", True),
            result.get("aiStatus", "generated"),
            bool(result.get("cacheHit")),
            timings,
            total_ms,
        )
        return jsonify(_public_ai_analysis_payload(result))
    except Exception:
        current_app.logger.exception(
            "AI 리포트 요청 예외: stage=%s timings=%s elapsed_ms=%s",
            stage,
            timings,
            round((time.perf_counter() - request_started) * 1000, 1),
        )
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
            ocid, basic, basic_response = _resolve_character_for_ai(name)
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
