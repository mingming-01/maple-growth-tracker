"""AI 성장 분석과 캐릭터 비교의 프롬프트·모델 호출을 담당한다."""
import hashlib
import json
import logging
import re
import time
from concurrent.futures import Future
from threading import Lock

import requests
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import current_app, has_app_context, has_request_context, request
from datetime import date, datetime, timezone
from types import SimpleNamespace

from tracker.integrations.ai_provider import (
    ProviderError,
    ProviderText,
    provider_error_type,
    provider_retry_after_seconds,
    request_gemini,
    request_openrouter,
    should_use_openrouter,
)
from tracker.services.ai_text_service import (
    REQUIRED_GROWTH_SECTIONS,
    sanitize_ai_text,
    validate_growth_report,
)
from tracker.services.performance_metrics import increment_metric
from tracker.runtime import (
    get_ai_response_cache,
    get_ai_response_cache_metadata,
    get_gemini_client,
    get_runtime_state,
    set_ai_response_cache,
)


def _is_quota_error(error):
    return provider_error_type(error) == "provider_quota" or "RESOURCE_EXHAUSTED" in str(error).upper()


def _request_deadline():
    """요청 시작부터 최대 90초의 전체 AI deadline을 적용한다."""
    total = 90.0
    started = None
    if has_request_context():
        started = request.environ.get("maple_request_started_at")
        try:
            total = min(90.0, max(5.0, float(current_app.config.get("AI_REQUEST_TOTAL_TIMEOUT", 90.0))))
        except (TypeError, ValueError):
            pass
    if started is None:
        started = time.monotonic()
    return float(started) + total


_PROVIDER_LOG_FIELDS = (
    "provider", "model_alias", "selected_model", "selected_provider",
    "http_status", "elapsed_ms", "response_bytes", "response_body_present",
    "candidate_count", "choice_count", "has_choices", "has_message", "content_present",
    "content_length", "content_type", "reasoning_present", "reasoning_length",
    "finish_reason", "native_finish_reason", "response_classification", "timeout_phase", "attempt", "provider_error_code",
    "expected_response_bytes", "body_complete", "transfer_encoding",
    "response_content_type", "response_content_encoding", "response_server",
    "response_request_id", "cause_class", "context_class",
    "stream_event_count", "stream_done", "stream_reasoning_bytes",
)
_SAFE_USAGE_FIELDS = (
    "prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens",
    "promptTokenCount", "candidatesTokenCount", "totalTokenCount", "thoughtsTokenCount",
)


def _safe_provider_metadata(metadata):
    source = metadata if isinstance(metadata, dict) else {}
    safe = {key: source[key] for key in _PROVIDER_LOG_FIELDS if key in source}
    for key in ("provider", "model_alias", "selected_model", "selected_provider", "response_classification"):
        if safe.get(key) is not None:
            safe[key] = str(safe[key])[:120]
    usage = source.get("usage")
    if isinstance(usage, dict):
        safe["usage"] = {
            key: usage[key] for key in _SAFE_USAGE_FIELDS
            if isinstance(usage.get(key), (int, float)) and not isinstance(usage.get(key), bool)
        }
    return safe


def _log_provider_failure(provider, error, started_at, deadline, attempt=1):
    """Record classified failure metadata only; never log request or response text."""
    now = time.monotonic()
    response = getattr(error, "response", None)
    metadata = getattr(error, "provider_metadata", None) or getattr(error, "http_metadata", None) or {}
    provider_error_code = metadata.get("provider_error_code") if isinstance(metadata, dict) else None
    if provider_error_code is None and response is not None:
        try:
            error_payload = json.loads(response.text or "")
            error_object = error_payload.get("error") if isinstance(error_payload, dict) else None
            provider_error_code = error_object.get("code") if isinstance(error_object, dict) else None
        except (TypeError, ValueError, AttributeError):
            provider_error_code = None
    http_status = (
        metadata.get("http_status") if isinstance(metadata, dict) else None
    ) or getattr(error, "status_code", None) or getattr(response, "status_code", None)
    details = {
        "provider": provider,
        "error_type": provider_error_type(error),
        "exception_class": type(error).__name__,
        "timeout_phase": (metadata.get("timeout_phase") if isinstance(metadata, dict) and metadata.get("timeout_phase") else None) or (
            "connect" if isinstance(error, requests.ConnectTimeout) else
            "response_read" if isinstance(error, requests.ReadTimeout) else
            "total_deadline" if provider_error_type(error) == "provider_timeout" else None
        ),
        "elapsed_ms": round((now - started_at) * 1000, 1),
        "deadline_remaining_ms": max(0, round((float(deadline) - now) * 1000, 1)),
        "http_status": http_status,
        "provider_error_code": str(provider_error_code)[:80] if provider_error_code is not None else None,
        "validation_failure_reason": getattr(error, "validation_reason", None),
        "finish_reason": getattr(error, "finish_reason", None),
        "attempt": int(attempt),
        "retry_count": max(0, int(attempt) - 1),
        "response": _safe_provider_metadata(metadata),
    }
    message = json.dumps(details, ensure_ascii=False, sort_keys=True)
    logger = current_app.logger if has_app_context() else logging.getLogger(__name__)
    logger.warning("AI provider request failed: %s", message)


def _log_provider_success(provider, metadata, *, validated, returned, cache_hit):
    details = _safe_provider_metadata(metadata)
    details.update({
        "provider": provider,
        "backend_validated": bool(validated),
        "report_returned": bool(returned),
        "cache_hit": bool(cache_hit),
    })
    message = json.dumps(details, ensure_ascii=False, sort_keys=True)
    logger = current_app.logger if has_app_context() else logging.getLogger(__name__)
    logger.info("AI provider request succeeded: %s", message)
    return details


def _log_ai_cache_failure(operation, error):
    """AI 응답 캐시 장애는 분석 공급자 장애와 분리해 기록한다."""
    details = {
        "operation": operation,
        "exception_class": type(error).__name__,
    }
    message = json.dumps(details, ensure_ascii=False, sort_keys=True)
    if has_app_context():
        current_app.logger.warning("AI 응답 캐시 작업 실패(분석은 계속 진행): %s", message)
    else:
        logging.getLogger(__name__).warning(
            "AI 응답 캐시 작업 실패(분석은 계속 진행): %s", message
        )


def _get_cached_ai_response(cache_key):
    """캐시 조회가 실패해도 공급자 분석 경로를 계속 사용한다."""
    try:
        return get_ai_response_cache(cache_key)
    except Exception as error:
        _log_ai_cache_failure("read", error)
        return None


def _get_cached_ai_response_metadata(cache_key):
    """캐시 본문 조회와 분리해 기존 생성 메타데이터를 안전하게 읽는다."""
    try:
        return get_ai_response_cache_metadata(cache_key) or {}
    except Exception as error:
        _log_ai_cache_failure("read_metadata", error)
        return {}


def _store_cached_ai_response(cache_key, analysis, metadata=None):
    """공급자가 만든 정상 분석문과 선택적 출처 정보를 캐시한다."""
    try:
        if metadata is None:
            set_ai_response_cache(cache_key, analysis)
        else:
            set_ai_response_cache(cache_key, analysis, metadata=metadata)
        return True
    except Exception as error:
        _log_ai_cache_failure("write", error)
        return False


def _build_generation_metadata(provider, provider_metadata=None, *, fallback_used=False, fallback_reason=None):
    """실제 생성 제공자·모델과 폴백 여부만 응답 및 캐시에 보존한다."""
    safe = _safe_provider_metadata(provider_metadata)
    requested_model = safe.get("model_alias")
    selected_model = safe.get("selected_model")
    return {
        "provider": str(provider or "unknown"),
        "requestedModel": str(requested_model)[:120] if requested_model else None,
        "selectedModel": str(selected_model)[:120] if selected_model else None,
        "selectedProvider": str(safe.get("selected_provider"))[:120] if safe.get("selected_provider") else None,
        "fallbackUsed": bool(fallback_used),
        "fallbackReason": str(fallback_reason)[:80] if fallback_used and fallback_reason else None,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _gemini_cooldown_remaining(runtime_state):
    try:
        until = runtime_state.ai_provider_state_store.get_cooldown_until("gemini")
        return max(0.0, float(until) - time.time())
    except Exception as error:
        # 상태 저장소 장애는 분석 자체를 중단하지 않는다.
        print(f"Gemini 쿨다운 상태 조회를 건너뜁니다: {type(error).__name__}")
        return 0.0


def _set_gemini_cooldown(runtime_state, error):
    default_seconds = 300
    try:
        default_seconds = int(current_app.config.get("GEMINI_QUOTA_COOLDOWN_SECONDS", default_seconds))
    except Exception:
        pass
    delay = provider_retry_after_seconds(error, default_seconds)
    try:
        runtime_state.ai_provider_state_store.set_cooldown_until("gemini", time.time() + delay)
    except Exception as store_error:
        print(f"Gemini 쿨다운 저장을 건너뜁니다: {type(store_error).__name__}")
    return delay


def _clear_gemini_cooldown(runtime_state):
    # 만료된 timestamp는 읽기 시점에 자동으로 무시한다. 동시 worker가 새로
    # 기록한 quota cooldown을 성공 요청이 지워버리지 않도록 여기서는 삭제하지 않는다.
    return None


def _error_result(error, fallback_message):
    """공급자 오류를 HTTP 계층에서 구분할 수 있는 안전한 형태로 변환한다."""
    error_type = provider_error_type(error)
    status_code = 429 if error_type == "provider_quota" else (
        503 if error_type in {"provider_timeout", "provider_unavailable"} else 502
    )
    result = {
        "error": (
            "AI 분석 사용량 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
            if error_type == "provider_quota" else fallback_message
        ),
        "statusCode": status_code,
        "errorType": error_type,
    }
    if error_type == "provider_quota":
        result["retryAfterSeconds"] = provider_retry_after_seconds(error)
    return result


def _fallback_failure_result(primary_error, fallback_error=None):
    """기본 공급자와 대체 공급자의 실패 유형을 구조화해 반환한다."""
    if fallback_error is None:
        if primary_error is None:
            return {
                "error": "AI 분석을 사용할 수 없습니다.",
                "statusCode": 503,
                "errorType": "provider_unavailable",
            }
        result = _error_result(primary_error, "AI 분석을 불러오지 못했습니다.")
        return result
    if primary_error is None:
        return _error_result(fallback_error, "AI 분석을 불러오지 못했습니다.")
    return {
        "error": "기본 AI와 대체 AI 분석 요청이 모두 실패했습니다. 잠시 후 다시 시도해주세요.",
        "statusCode": 503,
        "errorType": "provider_fallback_failed",
        "primaryErrorType": provider_error_type(primary_error),
        "fallbackErrorType": provider_error_type(fallback_error),
        "primaryHttpStatus": _provider_http_status(primary_error),
        "fallbackHttpStatus": _provider_http_status(fallback_error),
        "primaryException": type(primary_error).__name__,
        "fallbackException": type(fallback_error).__name__,
        "primaryProviderMetadata": _safe_provider_metadata(
            getattr(primary_error, "provider_metadata", None) or getattr(primary_error, "http_metadata", None)
        ),
        "fallbackProviderMetadata": _safe_provider_metadata(
            getattr(fallback_error, "provider_metadata", None) or getattr(fallback_error, "http_metadata", None)
        ),
    }


def _provider_http_status(error):
    response = getattr(error, "response", None)
    metadata = getattr(error, "provider_metadata", None) or getattr(error, "http_metadata", None)
    status = (
        (metadata.get("http_status") if isinstance(metadata, dict) else None)
        or getattr(error, "status_code", None)
        or getattr(response, "status_code", None)
    )
    return status if isinstance(status, int) and 100 <= status <= 599 else None


def _generate_gemini_content(client_or_prompt, prompt=None, api_key=None, deadline=None):
    """Gemini 호출을 제한 시간 REST 어댑터로 전달한다.

    두 인자 호출은 구버전 단위 테스트·외부 호출부와의 호환성을 위해 남긴다.
    실제 애플리케이션 경로는 프롬프트 한 인자로 호출해 전체 시간 제한을 적용한다.
    """
    if prompt is not None:
        return client_or_prompt.models.generate_content(
            model="gemini-3.6-flash", contents=prompt
        )
    return SimpleNamespace(text=request_gemini(client_or_prompt, api_key=api_key, deadline=deadline))


def _require_provider_text(value, provider):
    if not isinstance(value, str) or not value.strip():
        raise ProviderError(f"{provider} 응답에 분석 텍스트가 없습니다.", "provider_empty_response")
    text = value.strip()
    return ProviderText(text, getattr(value, "provider_metadata", {})) if isinstance(value, ProviderText) else text



def _deterministic_growth_forecast(character, metrics):
    """계산된 목표 레벨과 날짜를 사용해 성장 전망을 일관되게 작성한다."""
    prediction = (metrics or {}).get("prediction")
    if not isinstance(prediction, dict):
        return "현재 기록만으로는 다음 레벨업 날짜를 예상하기 어려워요."
    try:
        parsed_date = date.fromisoformat(str(prediction.get("estimatedDate")))
        target_level = int(prediction.get("nextLevel"))
        current_level = int(character.get("level"))
    except (TypeError, ValueError):
        return "현재 기록만으로는 다음 레벨업 날짜를 예상하기 어려워요."
    if target_level != current_level + 1 or target_level <= 0:
        return "현재 기록만으로는 다음 레벨업 날짜를 예상하기 어려워요."
    date_label = f"{parsed_date.month}월 {parsed_date.day}일"
    return (
        f"최근처럼 경험치를 얻는다면 {date_label}쯤 "
        f"{target_level}레벨에 도달할 것으로 예상돼요. "
        "실제 레벨업 날짜는 앞으로의 성장 속도에 따라 달라질 수 있어요."
    )


def _apply_deterministic_growth_forecast(analysis, character, metrics):
    """AI의 전망 해석은 보존하고 서버가 계산한 정확한 전망 문장을 덧붙인다."""
    forecast = _deterministic_growth_forecast(character, metrics)
    pattern = r"(\[성장 전망\])([\s\S]*?)(?=\n\[AI 코멘트\])"

    def append_server_forecast(match):
        ai_text = match.group(2).strip()
        if forecast and forecast not in ai_text:
            ai_text = f"{ai_text}\n{forecast}" if ai_text else forecast
        return f"{match.group(1)}\n{ai_text}"

    return re.sub(pattern, append_server_forecast, analysis, count=1)


def _build_ai_commentary_context(source_data):
    """서버 계산 결과를 숫자가 없는 정성 신호로 변환해 AI에 전달한다."""
    source_data = source_data if isinstance(source_data, dict) else {}
    metrics = source_data.get("metrics") or {}
    insights = source_data.get("growthInsights") or {}
    selected_period = source_data.get("selectedPeriod") or {}
    summary = selected_period.get("periodSummary") or {}
    basis = insights.get("basis") or {}

    comparison = insights.get("weekOverWeek") or {}
    direction = comparison.get("direction")
    change_percent = comparison.get("averageDailyGrowthChangePercent")
    try:
        magnitude = abs(float(change_percent))
    except (TypeError, ValueError):
        magnitude = None

    period_days = selected_period.get("periodDays", 7)
    if period_days in (30, 90):
        growth_comparison = "선택한 장기 구간의 전체 성장 기록을 중심으로 해석"
    elif comparison.get("status") != "available" or direction in (None, "insufficient", "insufficient_data"):
        growth_comparison = "비교할 이전 성장 기록이 충분하지 않음"
    elif direction == "increase":
        growth_comparison = (
            "이전보다 성장 속도가 뚜렷하게 높아짐" if magnitude is not None and magnitude >= 20
            else "이전보다 성장 속도가 완만하게 높아짐" if magnitude is not None and magnitude >= 5
            else "이전보다 성장 속도가 소폭 높아짐"
        )
    elif direction == "decrease":
        growth_comparison = (
            "이전보다 성장 속도가 뚜렷하게 낮아짐" if magnitude is not None and magnitude >= 20
            else "이전보다 성장 속도가 완만하게 낮아짐" if magnitude is not None and magnitude >= 5
            else "이전보다 성장 속도가 소폭 낮아짐"
        )
    else:
        growth_comparison = "이전 기간과 비슷한 성장 흐름"

    coverage = summary.get("coveragePercent")
    if coverage is None:
        coverage = basis.get("coveragePercent")
    try:
        coverage_value = float(coverage)
    except (TypeError, ValueError):
        coverage_value = None
    if coverage_value is None:
        record_coverage = "기록 충실도를 판단할 자료가 부족함"
    elif coverage_value >= 85:
        record_coverage = "분석 기간의 기록이 비교적 충실함"
    elif coverage_value >= 60:
        record_coverage = "분석 기간 중 일부 날짜의 기록이 비어 있음"
    else:
        record_coverage = "분석 기간의 기록이 충분하지 않음"

    level_ups = metrics.get("levelUps")
    if isinstance(level_ups, list) and level_ups:
        level_transition = "분석 기간 중 레벨업 전환이 확인됨"
    elif summary.get("levelUpIntervals"):
        level_transition = "레벨업 전환은 관찰됐지만 날짜나 전후 레벨을 확정할 수 없음"
    elif summary.get("validGrowthIntervals") in (None, 0):
        level_transition = "레벨업 여부를 판단할 연속 기록이 부족함"
    else:
        level_transition = "분석 기간의 확인된 기록에서 레벨업 전환이 나타나지 않음"

    progress = (metrics.get("levelProgress") or {}).get("currentRate")
    try:
        progress_value = float(progress)
    except (TypeError, ValueError):
        progress_value = None
    if progress_value is None:
        current_progress = "현재 레벨 진행 단계를 판단할 자료가 부족함"
    elif progress_value >= 80:
        current_progress = "현재 레벨의 후반 진행 구간"
    elif progress_value >= 35:
        current_progress = "현재 레벨의 중간 진행 구간"
    else:
        current_progress = "현재 레벨의 초반 진행 구간"

    prediction = metrics.get("prediction")
    forecast = (
        "서버에서 참고 가능한 성장 전망을 계산함"
        if isinstance(prediction, dict) and prediction.get("estimatedDate")
        else "기록만으로 신뢰할 수 있는 성장 전망을 계산하기 어려움"
    )
    period_scope = "장기 성장 기록의 흐름" if period_days in (30, 90) else "최근 성장 기록의 흐름"

    commentary_context = {
        "분석 범위": period_scope,
        "이전 기간 대비 성장 흐름": growth_comparison,
        "기록 충실도": record_coverage,
        "레벨업 관찰": level_transition,
        "현재 레벨 진행 단계": current_progress,
        "성장 전망 자료": forecast,
    }
    if period_days in (30, 90):
        period_trend = metrics.get("periodTrend") or {}
        if period_trend.get("status") != "available":
            long_period_signal = "기간 초반과 후반을 비교할 만큼 확인된 경험치 변화 기록이 충분하지 않음"
        else:
            direction = period_trend.get("direction")
            strength = period_trend.get("strength")
            if direction == "increase" and strength == "strong":
                long_period_signal = "기간 후반의 하루 평균 경험치 증가량이 초반보다 뚜렷하게 높아짐"
            elif direction == "increase" and strength == "moderate":
                long_period_signal = "기간 후반의 하루 평균 경험치 증가량이 초반보다 완만하게 높아짐"
            elif direction == "increase":
                long_period_signal = "기간 후반의 경험치 증가량이 초반보다 높지만 초반 기준값이 작아 변화 폭을 단정하기 어려움"
            elif direction == "decrease" and strength == "strong":
                long_period_signal = "기간 후반의 하루 평균 경험치 증가량이 초반보다 뚜렷하게 낮아짐"
            elif direction == "decrease" and strength == "moderate":
                long_period_signal = "기간 후반의 하루 평균 경험치 증가량이 초반보다 완만하게 낮아짐"
            elif direction == "decrease":
                long_period_signal = "기간 후반의 경험치 증가량이 초반보다 낮지만 변화 폭은 크지 않음"
            else:
                long_period_signal = "기간 초반과 후반의 하루 평균 경험치 증가량이 대체로 비슷함"
        commentary_context["선택 기간 내 초반과 후반의 성장 흐름"] = long_period_signal

    return commentary_context


def _build_growth_report_prompt(source_data):
    """수치 원문 대신 백엔드가 분류한 정성 신호만 AI 코멘트에 제공한다."""
    commentary_context = _build_ai_commentary_context(source_data)
    return f"""
너는 메이플스토리 캐릭터의 성장 기록을 플레이어와 함께 살펴보는 친근한 성장 코치야.
친근하고 자연스러운 해요체를 사용하고, 메이플스토리에서 익숙한 경험치·레벨업 표현을 우선해. 딱딱한 보고서 말투보다 실제 플레이어에게 이야기하듯 담백하게 작성해.

[역할]
- 백엔드가 계산한 사실을 다시 계산하지 말고, 제공된 정성 신호를 바탕으로 성장 과정에서 눈에 띄는 양상과 그 의미를 설명해.
- 성장 흐름, 기록의 충실도, 레벨업 전후의 상황을 서로 자연스럽게 연결해. 신호를 그대로 나열하거나 앞의 리포트 내용을 반복하지 마.
- 30일·90일 분석에서 '선택 기간 내 초반과 후반의 성장 흐름' 신호가 있으면 이를 핵심 해석에 반영해. 이는 선택 기간 내부 비교이며, 선택 기간 이전의 기록과 비교했다는 뜻으로 바꾸지 마.
- 기록에 없는 사냥 방식, 플레이 시간, 접속 습관, 장비 효과, 성장 원인을 추측하지 마.
- 신호가 부족하면 단정하지 말고 무엇을 판단하기 어려운지 솔직하게 밝혀.

[해석과 문체]
- 가능한 경우 '확인된 흐름 → 그 흐름이 보여주는 의미 → 다음에 살펴볼 점 또는 짧은 응원'으로 자연스럽게 이어가. 이 순서를 모든 문장에 억지로 적용하지는 마.
- 성장 속도가 낮아진 신호가 있으면 그 사실을 숨기지 말되, 성장이 멈췄다고 과장하지 마. 기록 공백을 성장 정체나 미접속의 증거로 해석하지 마.
- 레벨업이 확인됐다면 그 성취나 새 레벨에서 이어지는 성장을 자연스럽게 짚어도 좋아. 확인되지 않은 레벨업을 축하하거나 성과를 만들어내지는 마.
- 응원은 전체 분석과 연결되는 짧고 구체적인 표현으로 필요할 때 한 번만 덧붙여. 과장된 칭찬, 상투적인 격려, 뜬금없는 응원, 플레이를 강요하는 표현은 피해야 해.
- 기록만으로 말할 수 있는 내용이 적다면 억지로 풍성하게 쓰지 말고, 짧더라도 정확하고 따뜻하게 마무리해.
- 모든 문장은 리포트 본문과 같은 존댓말 해요체로 통일해. 문장 중간이나 끝에서 반말로 바꾸지 마.
- '보여', '있어', '좋아', '할게', '볼게', '거야'처럼 반말로 읽히는 끝맺음과 평서형 '-다' 체는 사용하지 마.

[정확성 규칙]
- 제공된 정성 신호에 없는 성장 방향이나 원인을 만들어내지 마.
- 수치·날짜·평균·비율·원인·행동을 새로 계산하거나 추측하지 마.
- 숫자·날짜·퍼센트·레벨 번호·경험치 단위·횟수는 쓰지 마. 정확한 수치와 날짜는 백엔드가 리포트에 별도로 작성해.
- 서로 다른 레벨의 경험치 진행률을 직접 비교하거나 레벨업 당일의 경험치 획득량을 추정하지 마.

[출력 형식]
- AI 코멘트 본문만 작성해. 제목, 구분 표시, 목록, 표, 마크다운, 코드, 영어 상태값은 쓰지 마.
- 자연스럽고 구체적인 한국어 해요체로 두세 문장만 작성해. 길게 설명하거나 여러 내용을 한꺼번에 나열하지 마.
- 리포트 앞부분에 표시된 숫자와 날짜를 반복하지 말고, 플레이어가 성장 흐름을 이해하는 데 도움이 되는 해석과 다음에 살펴볼 점을 중심으로 작성해.

[백엔드가 계산한 정성 신호]
{json.dumps(commentary_context, ensure_ascii=False)}
"""


def _format_experience_korean(value):
    """큰 경험치는 대표 단위 하나로 줄여 소수점 첫째 자리까지 표시한다."""
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            return None
    except (InvalidOperation, TypeError, ValueError):
        return None

    sign = "-" if number < 0 else ""
    absolute = abs(number)
    units = (
        ("경", Decimal(10**16)),
        ("조", Decimal(10**12)),
        ("억", Decimal(10**8)),
        ("만", Decimal(10**4)),
    )
    for index, (unit_name, unit_value) in enumerate(units):
        if absolute >= unit_value:
            amount = (absolute / unit_value).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
            # 반올림 결과가 다음 큰 단위를 넘으면 표시 단위도 올린다.
            if amount >= Decimal("10000") and index > 0:
                unit_name, unit_value = units[index - 1]
                amount = (absolute / unit_value).quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP
                )
            return f"{sign}{amount:,.1f}{unit_name}"
    rounded = number.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{rounded:,.0f}"


def _format_period_date_range(start_value, end_value):
    """ISO 날짜 구간을 혼동 없는 한국어 날짜 구간으로 표시한다."""
    try:
        start = date.fromisoformat(str(start_value))
        end = date.fromisoformat(str(end_value))
    except (TypeError, ValueError):
        return None
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.month}월 {start.day}일~{end.day}일"
    return f"{start.month}월 {start.day}일~{end.month}월 {end.day}일"


def _build_growth_report_cache_key(prompt, source_data):
    """정성 신호 프롬프트와 해당 캐릭터의 실제 계산 데이터로 캐시를 구분한다."""
    return (
        prompt
        + "\n[리포트 형식 버전] 9\n"
        + "[캐시 식별 데이터]\n"
        + json.dumps(source_data, ensure_ascii=False, sort_keys=True)
    )


def _growth_report_fact_error(report, source_data):
    """AI가 작성한 수치와 날짜가 서버가 제공한 데이터에 존재하는지 확인한다."""
    allowed_numbers = set()
    allowed_dates = set()
    allowed_number_units = set()

    def add_number(value):
        try:
            number = Decimal(str(value).replace(",", "").strip())
            if number.is_finite():
                allowed_numbers.add(format(number.normalize(), "f"))
                allowed_numbers.add(format(number.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), "f"))
        except (InvalidOperation, TypeError, ValueError):
            return

    def walk(value, key=""):
        if isinstance(value, dict):
            for child_key, child in value.items():
                walk(child, str(child_key))
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child, key)
        elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            add_number(value)
            normalized_key = key.casefold()
            if any(term in normalized_key for term in ("experience", "growth", "sum", "average")):
                formatted = _format_experience_korean(value)
                if formatted:
                    for token, unit in re.findall(r"(\d+(?:\.\d+)?)(경|조|억|만)", formatted.replace(",", "")):
                        allowed_numbers.add(token)
                        allowed_number_units.add((token, unit))
            if any(term in normalized_key for term in ("rate", "percent", "coverage", "change")):
                rounded = Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                add_number(rounded)
                allowed_number_units.add((format(rounded.normalize(), "f"), "%"))
            if "level" in normalized_key:
                allowed_number_units.add((format(Decimal(str(value)).normalize(), "f"), "레벨"))
            if "interval" in normalized_key or "count" in normalized_key:
                allowed_number_units.add((format(Decimal(str(value)).normalize(), "f"), "회"))
            if "perioddays" in normalized_key:
                allowed_number_units.add((format(Decimal(str(value)).normalize(), "f"), "일"))
        elif isinstance(value, str):
            for match in re.finditer(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)", value):
                year, month, day = map(int, match.groups())
                try:
                    parsed = date(year, month, day)
                except ValueError:
                    continue
                allowed_dates.add((parsed.month, parsed.day))
                add_number(year)
                add_number(month)
                add_number(day)
                allowed_number_units.add((str(month), "월"))
                allowed_number_units.add((str(day), "일"))
            for match in re.finditer(r"(\d{1,2})월\s*(\d{1,2})일", value):
                allowed_dates.add((int(match.group(1)), int(match.group(2))))
                add_number(match.group(1))
                add_number(match.group(2))
                allowed_number_units.add((str(int(match.group(1))), "월"))
                allowed_number_units.add((str(int(match.group(2))), "일"))

    walk(source_data or {})
    # 기간 길이·레벨·비율처럼 모델이 단위를 붙여 표현할 수 있는 값도 허용 목록에 포함한다.
    for key in ("periodDays", "level", "currentLevel", "previousLevel", "currentRate", "remainingRate"):
        value = (source_data or {}).get(key)
        if isinstance(value, (int, float)):
            add_number(value)

    for match in re.finditer(r"(?<!\d)(\d{1,2})월\s*(\d{1,2})일", report):
        if (int(match.group(1)), int(match.group(2))) not in allowed_dates:
            return "unsupported_date"

    for token in re.findall(r"(?<![A-Za-z])\d+(?:,\d{3})*(?:\.\d+)?", report):
        normalized = token.replace(",", "")
        try:
            number = format(Decimal(normalized).normalize(), "f")
        except InvalidOperation:
            return "unsupported_number"
        if number not in allowed_numbers:
            return "unsupported_number"

    for number, unit in re.findall(
        r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(경|조|억|만|%p|%|레벨|회|일|위)",
        report,
    ):
        normalized = format(Decimal(number.replace(",", "")).normalize(), "f")
        if (normalized, unit) not in allowed_number_units:
            return "unsupported_number_unit"
    return True


def _validate_growth_report_facts(report, source_data):
    """Boolean compatibility wrapper around the categorized fact check."""
    return _growth_report_fact_error(report, source_data) is True


def _extract_ai_comment(value):
    """Extract only the AI commentary; factual report sections are always server-owned."""
    text = str(value or "")
    # Some providers/test doubles emit escaped line breaks as literal \n sequences.
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n").strip()
    if not text:
        return ""

    ai_heading = re.search(r"(?im)^\s*\[AI\s*코멘트\]\s*", text)
    if ai_heading:
        text = text[ai_heading.end():]
        next_heading = re.search(
            r"(?im)^\s*\[(?:성장\s*패턴|성장\s*변화|성장\s*분석|레벨업\s*분석|레벨업|성장\s*전망)\]\s*",
            text,
        )
        if next_heading:
            text = text[:next_heading.start()]
    elif re.search(
        r"(?im)^\s*\[(?:성장\s*패턴|성장\s*변화|성장\s*분석|레벨업\s*분석|레벨업|성장\s*전망)\]\s*",
        text,
    ):
        # A full model-written report without an explicit AI-comment section is not commentary.
        return ""

    return text.strip()


def _remove_numeric_comment_sentences(comment):
    """AI 코멘트의 숫자 포함 문장만 제거하고 서버가 제공할 사실과 분리한다."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", str(comment or ""))
    kept = []
    removed = False
    for sentence in sentences:
        text = sentence.strip()
        if not text:
            continue
        if re.search(r"\d", text):
            removed = True
            continue
        kept.append(text)
    return " ".join(kept), removed


_INFORMAL_COMMENT_ENDING = re.compile(
    r"(?:보여|볼게|해\s*볼게|해볼게|할게|할\s*거야|거야|이야|야|같아|좋아|"
    r"있어|없어|돼|해|했어|했지|하자|크다|작다|높다|낮다|맞아|아니야|구나|"
    r"겠지|하네|그렇네|많아|적어|필요해|어려워|좋겠네|괜찮아|맞네|해봐|해줘)$"
)


def _has_informal_comment_tone(comment):
    """끝맺음에서 명확한 반말 표현이 발견되는지 보수적으로 확인한다."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", str(comment or ""))
    for sentence in sentences:
        ending = sentence.strip().rstrip("\"'”’)]}")
        if not ending:
            continue
        if _INFORMAL_COMMENT_ENDING.search(ending):
            return True
        if ending.endswith("다") and not re.search(
            r"(?:습니다|입니다|합니다|됩니다|있습니다|없습니다|했습니다|됐습니다|드립니다)$",
            ending,
        ):
            return True
    return False


def _prepare_ai_comment(value, expected_date, source_data):
    """Keep usable, consistently polite prose; numeric facts remain server-owned."""
    sanitized = sanitize_ai_text(value, expected_date)
    comment = _extract_ai_comment(sanitized)
    comment, removed_numeric_sentences = _remove_numeric_comment_sentences(comment)
    compact = re.sub(r"[\s.!?…·]", "", comment)
    if len(compact) < 8:
        reason = "numeric_claim_only" if removed_numeric_sentences else "empty_comment"
        return None, reason
    if _has_informal_comment_tone(comment):
        return None, "informal_tone"
    return comment, None


def _server_fallback_growth_report(
    character, metrics, growth_insights, analysis_context, reason="provider_unavailable"
):
    """Return a clearly-labelled deterministic report when no AI commentary is usable."""
    fallback_comment = (
        "이번 요청에서는 AI 코멘트를 생성하지 못했어요. "
        "아래 성장 수치와 레벨업 정보는 저장된 기록을 바탕으로 서버가 계산한 내용이에요."
    )
    report = _build_deterministic_growth_report(
        character, metrics, growth_insights, analysis_context, fallback_comment
    )
    metadata = _log_provider_success(
        "server_fallback",
        {"response_classification": "deterministic_fallback"},
        validated=True,
        returned=True,
        cache_hit=False,
    )
    return {
        "analysis": report,
        "cacheHit": False,
        "growthInsights": growth_insights,
        "aiGenerated": False,
        "aiStatus": "fallback",
        "aiFallbackReason": str(reason or "provider_unavailable")[:80],
        "providerMetadata": metadata,
    }


def _compose_growth_report_from_ai(
    response_text, character, metrics, growth_insights, analysis_context,
    source_data, expected_date, provider,
):
    """Keep AI prose, while the backend supplies every measured fact and section."""
    comment, validation_reason = _prepare_ai_comment(
        response_text, expected_date, source_data
    )
    if validation_reason:
        error = ProviderError(
            f"{provider} AI commentary failed validation.",
            "provider_invalid_output",
        )
        error.validation_reason = validation_reason
        error.provider_metadata = {
            **dict(getattr(response_text, "provider_metadata", {}) or {}),
            "response_classification": "comment_validation_failed",
        }
        raise error

    return _build_deterministic_growth_report(
        character, metrics, growth_insights, analysis_context, comment
    )


def _build_deterministic_growth_report(character, metrics, growth_insights, analysis_context, ai_comment):
    """수치·날짜·레벨 진행률은 서버 계산값으로만 리포트에 작성한다."""
    metrics = metrics or {}
    insights = growth_insights or {}
    period_days = (analysis_context or {}).get("periodDays", 7)
    recent = insights.get("recentPeriod") if period_days == 7 else None
    previous = insights.get("previousPeriod") if period_days == 7 else None
    summary = (
        recent
        or (analysis_context or {}).get("periodSummary")
        or metrics.get("periodSummary")
        or {}
    )

    period_label = _format_period_date_range(
        summary.get("startDate"), summary.get("endDate")
    )
    period_name = "최근 7일" if period_days == 7 else f"선택한 {period_days}일"

    total_text = _format_experience_korean(
        summary.get("experienceGainSum", summary.get("observedExperienceSum"))
    )
    average_text = _format_experience_korean(summary.get("averageDailyExperience"))
    valid_intervals = summary.get("validGrowthIntervals")

    if total_text and average_text and isinstance(valid_intervals, int):
        date_prefix = f"{period_label} 동안 " if period_label else ""
        growth_pattern = (
            f"{date_prefix}집계된 {valid_intervals}회의 일일 경험치 변화 합계는 "
            f"{total_text}이며, 변화가 확인된 날의 하루 평균은 {average_text}예요."
        )
    elif average_text:
        growth_pattern = f"{period_name}의 하루 평균 경험치는 {average_text}예요."
    else:
        growth_pattern = f"{period_name}은 경험치 변화 기록이 충분하지 않아 증가량을 확정하기 어려워요."

    comparison = insights.get("weekOverWeek") or {}
    previous_average = _format_experience_korean(
        (previous or {}).get("averageDailyExperience")
    )
    recent_average = _format_experience_korean(
        (recent or {}).get("averageDailyExperience")
    )
    change_percent = comparison.get("averageDailyGrowthChangePercent")

    if (
        period_days == 7
        and comparison.get("status") == "available"
        and previous_average
        and recent_average
        and isinstance(change_percent, (int, float))
    ):
        previous_range = _format_period_date_range(
            (previous or {}).get("startDate"), (previous or {}).get("endDate")
        )
        recent_range = _format_period_date_range(
            (recent or {}).get("startDate"), (recent or {}).get("endDate")
        )
        direction = comparison.get("direction")
        if direction == "increase":
            change_text = f"{abs(change_percent):.1f}% 늘었어요."
        elif direction == "decrease":
            change_text = f"{abs(change_percent):.1f}% 줄었어요."
        else:
            change_text = "큰 차이가 없어요."
        previous_label = f"직전 7일({previous_range})" if previous_range else "직전 7일"
        recent_label = f"최근 7일({recent_range})" if recent_range else "최근 7일"
        growth_change = (
            f"{previous_label}의 하루 평균은 {previous_average}, "
            f"{recent_label}은 {recent_average}로, 직전 기간보다 {change_text}"
        )
    elif period_days in (30, 90):
        previous_summary = (analysis_context or {}).get("previousPeriodSummary") or {}
        current_count = summary.get("validGrowthIntervals")
        previous_count = previous_summary.get("validGrowthIntervals")
        current_sum = summary.get(
            "experienceGainSum", summary.get("observedExperienceSum")
        )
        previous_sum = previous_summary.get(
            "experienceGainSum", previous_summary.get("observedExperienceSum")
        )
        minimum_intervals = max(4, (period_days * 2 + 4) // 5)

        enough_period_comparison = (
            isinstance(current_count, int)
            and isinstance(previous_count, int)
            and current_count >= minimum_intervals
            and previous_count >= minimum_intervals
            and current_sum is not None
            and previous_sum is not None
        )
        if enough_period_comparison:
            current_total = Decimal(str(current_sum))
            previous_total = Decimal(str(previous_sum))
            current_average = current_total / Decimal(current_count)
            previous_average = previous_total / Decimal(previous_count)
            current_average_text = _format_experience_korean(current_average)
            previous_average_text = _format_experience_korean(previous_average)

            if previous_total > 0:
                change_percent = (
                    (current_total * previous_count - previous_total * current_count)
                    * Decimal("100")
                    / (previous_total * current_count)
                )
                if change_percent > Decimal("0.5"):
                    change_text = f"이전 기간보다 {change_percent:.1f}% 늘었어요."
                elif change_percent < Decimal("-0.5"):
                    change_text = f"이전 기간보다 {abs(change_percent):.1f}% 줄었어요."
                else:
                    change_text = "이전 기간과 큰 차이가 없어요."
                growth_change = (
                    f"직전 {period_days}일의 하루 평균은 {previous_average_text}, "
                    f"선택한 {period_days}일은 {current_average_text}로, {change_text}"
                )
            elif current_total > 0:
                growth_change = (
                    f"직전 {period_days}일에는 확인된 경험치 증가가 없었고, "
                    f"선택한 {period_days}일에는 하루 평균 {current_average_text}의 "
                    "경험치 증가가 확인됐어요."
                )
            else:
                growth_change = (
                    f"직전 {period_days}일과 선택한 {period_days}일 모두 "
                    "확인된 경험치 증가가 거의 없어요."
                )
        else:
            period_trend = metrics.get("periodTrend") or {}
            trend_status = period_trend.get("status")
            trend_direction = period_trend.get("direction")
            trend_percent = period_trend.get("changePercent")
            if trend_status == "available" and trend_direction == "increase":
                detail = (
                    f"후반부의 하루 평균 경험치 증가량이 초반부보다 "
                    f"{abs(float(trend_percent)):.1f}% 높았어요."
                    if isinstance(trend_percent, (int, float))
                    else "후반부의 하루 평균 경험치 증가량이 초반부보다 높았어요."
                )
                growth_change = f"직전 기간과 비교할 기록은 충분하지 않지만, 선택한 {period_days}일 안에서는 {detail}"
            elif trend_status == "available" and trend_direction == "decrease":
                detail = (
                    f"후반부의 하루 평균 경험치 증가량이 초반부보다 "
                    f"{abs(float(trend_percent)):.1f}% 낮았어요."
                    if isinstance(trend_percent, (int, float))
                    else "후반부의 하루 평균 경험치 증가량이 초반부보다 낮았어요."
                )
                growth_change = f"직전 기간과 비교할 기록은 충분하지 않지만, 선택한 {period_days}일 안에서는 {detail}"
            elif trend_status == "available":
                growth_change = (
                    f"직전 기간과 비교할 기록은 충분하지 않지만, "
                    f"선택한 {period_days}일의 초반과 후반은 비슷한 성장 흐름을 보였어요."
                )
            elif average_text:
                growth_change = (
                    f"선택한 {period_days}일의 하루 평균은 {average_text}예요. "
                    "직전 기간과 기간 내 흐름을 비교할 만큼 기록이 충분하지 않아요."
                )
            else:
                growth_change = (
                    f"선택한 {period_days}일은 비교할 만큼 경험치 변화 기록이 충분하지 않아요."
                )
    elif average_text:
        growth_change = f"{period_name}의 하루 평균 경험치는 {average_text}로 확인됐어요. 비교할 이전 기간의 기록은 충분하지 않아요."
    else:
        growth_change = "이전 기간과 비교할 만큼 충분한 성장 기록이 아직 없어요."

    level_ups = metrics.get("levelUps") or []
    try:
        period_start_date = date.fromisoformat(str(summary.get("startDate")))
        period_end_date = date.fromisoformat(str(summary.get("endDate")))
        level_ups = [
            event for event in level_ups
            if period_start_date <= date.fromisoformat(str(event.get("date"))) <= period_end_date
        ]
    except (TypeError, ValueError):
        # 기간 경계를 알 수 없으면 원본 이벤트를 그대로 사용하되 날짜는 개별 파싱한다.
        pass

    if level_ups:
        level_sentences = []
        for event in level_ups:
            event_date = event.get("date")
            try:
                parsed = date.fromisoformat(str(event_date))
                date_label = f"{parsed.month}월 {parsed.day}일"
            except (TypeError, ValueError):
                date_label = None
            previous_level = event.get("previousLevel")
            current_level = event.get("currentLevel")
            if date_label and previous_level is not None and current_level is not None:
                level_sentences.append(
                    f"{date_label}에 {previous_level}레벨에서 {current_level}레벨로 올라갔어요."
                )
        level_up_text = " ".join(level_sentences) or "레벨업 전환이 기록에서 확인됐어요."
    else:
        level_up_count = (
            summary.get("levelUpIntervals")
            or (metrics.get("periodSummary") or {}).get("levelUpIntervals")
            or 0
        )
        if level_up_count:
            level_up_text = (
                f"선택 기간에 레벨업 전환 {int(level_up_count)}회가 확인됐지만, "
                "정확한 날짜와 레벨 변화는 확인된 연속 기록만으로 특정하지 않았어요."
            )
        else:
            level_up_text = "선택 기간의 연속된 기록에서는 레벨업 변화가 확인되지 않았어요."

    current_level = character.get("level")
    level_progress = metrics.get("levelProgress") or {}
    current_rate = level_progress.get("currentRate")
    progress_text = ""
    if isinstance(current_rate, (int, float)) and 0 <= current_rate <= 100:
        remaining_rate = max(0.0, 100.0 - float(current_rate))
        progress_text = (
            f" 현재 {current_level}레벨 경험치 진행률은 {float(current_rate):.1f}%이며, "
            f"다음 레벨까지 {remaining_rate:.1f}% 남았어요."
        )
    level_analysis = level_up_text + progress_text
    forecast = _deterministic_growth_forecast(character, metrics)

    report = (
        f"[성장 패턴]\n{growth_pattern}\n"
        f"[성장 변화]\n{growth_change}\n"
        f"[레벨업 분석]\n{level_analysis}\n"
        f"[성장 전망]\n{forecast}\n"
        f"[AI 코멘트]\n{ai_comment.strip()}"
    )
    if not validate_growth_report(report):
        raise ProviderError(
            "서버가 조립한 성장 리포트가 형식 검증을 통과하지 못했습니다.",
            "provider_invalid_output",
        )
    return report


def _filter_growth_history_to_selected_period(history, analysis_context):
    """기간 경계 계산에 사용한 직전 스냅샷은 AI의 선택 기간 서술에서 제외한다."""
    summary = (analysis_context or {}).get("periodSummary") or {}
    try:
        start = date.fromisoformat(str(summary.get("startDate")))
        end = date.fromisoformat(str(summary.get("endDate")))
    except (TypeError, ValueError):
        return list(history or [])
    filtered = []
    for item in history or []:
        try:
            item_date = date.fromisoformat(str(item.get("date")))
        except (TypeError, ValueError):
            continue
        if start <= item_date <= end:
            filtered.append(item)
    return filtered


def _generate_ai_analysis_impl(character, history, computed_metrics=None, growth_insights=None, analysis_context=None, force_refresh=False):
    runtime_state = get_runtime_state()
    gemini_api_key = getattr(runtime_state, "gemini_api_key", "")
    openrouter_api_key = getattr(runtime_state, "openrouter_api_key", "")
    deadline = _request_deadline()
    cooldown_remaining = _gemini_cooldown_remaining(runtime_state) if gemini_api_key else 0.0
    # Legacy 호출자는 computed_metrics를 넘기지 않는다. 기존 SDK 호출은
    # 호환성을 위해 유지하고, 웹 API의 정상 경로는 제한 시간이 있는 REST adapter를 쓴다.
    legacy_gemini_client = get_gemini_client() if computed_metrics is None else None

    growth_data = [
        {
            "date": item.get("date"),
            "level": item.get("level"),
            "experienceChange": item.get("experienceChange"),
            "ranking": item.get("ranking"),
            "rankingChange": item.get("rankingChange"),
            "levelUp": item.get("levelUp", False),
            "recordStatus": item.get("recordStatus"),
        }
        for item in history
    ]
    growth_data = _filter_growth_history_to_selected_period(
        growth_data, analysis_context
    )

    if computed_metrics is not None:
        prediction = computed_metrics.get("prediction")
        prediction_date = prediction.get("estimatedDate") if isinstance(prediction, dict) else None
        prediction_date_label = None
        if prediction_date:
            try:
                parsed_prediction_date = date.fromisoformat(str(prediction_date))
                prediction_date_label = f"{parsed_prediction_date.month}월 {parsed_prediction_date.day}일"
            except (TypeError, ValueError):
                prediction_date_label = None

        source_data = {
            "character": {
                "name": character.get("characterName"),
                "world": character.get("worldName"),
                "job": character.get("job"),
                "level": character.get("level"),
                "experienceRate": character.get("experienceRate"),
            },
            "metrics": computed_metrics,
            "growthInsights": growth_insights or {},
            "selectedPeriod": analysis_context or {"periodDays": 7, "periodSummary": None},
            "predictionDisplayDate": prediction_date_label,
            "history": growth_data,
        }
        prompt = _build_growth_report_prompt(source_data)
        # 모델에 전달하는 코멘트 프롬프트와 달리 캐시 키에는 해당 캐릭터의
        # 실제 계산 데이터 전체를 포함해 다른 캐릭터/기간의 리포트가 섞이지 않게 한다.
        cache_key = _build_growth_report_cache_key(prompt, source_data)
    else:
        required_sections = "\n".join(REQUIRED_GROWTH_SECTIONS)
        prompt = f"""
너는 메이플스토리 캐릭터의 성장 데이터를 해석하는 도우미야.
제공된 사실만 이용하고 경험치, 평균, 추세, 예측 날짜 등 숫자를 새로 계산하거나 미래를 추정하지 마.
경험치 증가는 '경험치 증가량' 또는 '경험치 획득량'이라고 표현하고 '경보'라는 단어는 사용하지 마.
기록이 부족한 경우 데이터 부족을 밝히고, 근거 없는 행동이나 플레이 스타일을 추측하지 마.
마크다운 없이 자연스러운 한국어 문장만 작성해. 개발용 키 이름, 영어 상태값, null, undefined를 답변에 쓰지 마.
아래 필수 구분 표시는 표시된 이름과 순서를 그대로 지켜 각각 한 번씩 사용해.
{required_sections}
성장 패턴과 변화는 제공된 날짜별 기록으로 확인되는 사실만 설명해.
레벨업 분석은 실제 레벨 변화가 기록에 있을 때만 설명해.
계산된 전망 지표가 제공되지 않았으므로 구체적인 레벨업 날짜나 남은 기간을 만들지 말고, 기록만으로 예측하기 어렵다면 그 점을 밝혀.
마지막 코멘트는 확인된 기록에 근거해 짧고 자연스럽게 작성해.

캐릭터:
{character.get("characterName")} / {character.get("worldName")} / Lv.{character.get("level")}
최근 성장 기록:
{json.dumps(growth_data, ensure_ascii=False)}
"""
        cache_key = prompt

    expected_date = None
    if computed_metrics is not None:
        prediction = computed_metrics.get("prediction")
        if isinstance(prediction, dict):
            expected_date = prediction.get("estimatedDate")

    cached_analysis = None if force_refresh else _get_cached_ai_response(cache_key)
    if cached_analysis is not None:
        if computed_metrics is not None:
            cached_analysis = _apply_deterministic_growth_forecast(
                cached_analysis, character, computed_metrics
            )
            # Cached output was assembled from server-owned metrics and a previously
            # validated commentary. Re-running a token/unit allowlist here can reject
            # legitimate server-written phrases (for example, a period expressed as days).
            if not validate_growth_report(cached_analysis):
                cached_analysis = None
        if cached_analysis is not None:
            cached_metadata = _get_cached_ai_response_metadata(cache_key)
            generation = cached_metadata.get("generation") if isinstance(cached_metadata, dict) else None
            if not isinstance(generation, dict):
                generation = None
            log_provider = generation.get("provider") if generation else "cache"
            log_metadata = {"response_body_present": True}
            if generation:
                log_metadata.update({
                    "model_alias": generation.get("requestedModel"),
                    "selected_model": generation.get("selectedModel"),
                    "selected_provider": generation.get("selectedProvider"),
                })
            print("저장된 AI 성장 리포트를 재사용했습니다.")
            metadata = _log_provider_success(log_provider, log_metadata, validated=True, returned=True, cache_hit=True)
            return {
                "analysis": cached_analysis,
                "cacheHit": True,
                "growthInsights": growth_insights,
                "aiGenerated": True,
                "aiStatus": "generated",
                "providerMetadata": metadata,
                "generation": generation,
                "delivery": {"source": "server_cache"},
            }

    gemini_error = None
    if gemini_api_key and cooldown_remaining > 0:
        gemini_error = ProviderError(
            "Gemini quota cooldown is active.",
            "provider_quota",
            retry_after_seconds=max(1, int(cooldown_remaining)),
        )
    elif gemini_api_key or legacy_gemini_client:
        gemini_started_at = time.monotonic()
        try:
            response = (
                _generate_gemini_content(legacy_gemini_client, prompt)
                if legacy_gemini_client is not None
                else _generate_gemini_content(prompt, api_key=gemini_api_key, deadline=deadline)
            )
            gemini_text = _require_provider_text(getattr(response, "text", None), "Gemini")
            provider_metadata = dict(getattr(gemini_text, "provider_metadata", {}) or {})
            provider_metadata["attempt"] = 1
            if computed_metrics is not None:
                analysis = _compose_growth_report_from_ai(
                    gemini_text,
                    character,
                    computed_metrics,
                    growth_insights,
                    analysis_context,
                    source_data,
                    expected_date,
                    "Gemini",
                )
            else:
                analysis = sanitize_ai_text(gemini_text, expected_date)
                if not validate_growth_report(analysis):
                    error = ProviderError("Gemini report format validation failed.", "provider_invalid_output")
                    error.validation_reason = "report_format"
                    error.provider_metadata = {**provider_metadata, "response_classification": "report_format_failed"}
                    raise error
            _clear_gemini_cooldown(runtime_state)
            generation = _build_generation_metadata("gemini", provider_metadata)
            _store_cached_ai_response(cache_key, analysis, metadata={"generation": generation})
            metadata = _log_provider_success("gemini", provider_metadata, validated=True, returned=True, cache_hit=False)
            return {
                "analysis": analysis,
                "cacheHit": False,
                "growthInsights": growth_insights,
                "aiGenerated": True,
                "aiStatus": "generated",
                "providerMetadata": metadata,
                "generation": generation,
                "delivery": {"source": "generated"},
            }
        except Exception as error:
            gemini_error = error
            if _is_quota_error(error):
                delay = _set_gemini_cooldown(runtime_state, error)
                print(f"Gemini 쿼터 제한으로 {delay}초 쿨다운을 적용했습니다.")
            _log_provider_failure("gemini", error, gemini_started_at, deadline)
            if not should_use_openrouter(error) and not openrouter_api_key and computed_metrics is None:
                return _error_result(error, "AI 분석을 불러오지 못했습니다.")

    if openrouter_api_key:
        openrouter_started_at = time.monotonic()
        try:
            response_text = _require_provider_text(
                request_openrouter(
                    prompt,
                    api_key=openrouter_api_key,
                    deadline=deadline,
                ),
                "OpenRouter",
            )
            provider_metadata = dict(getattr(response_text, "provider_metadata", {}) or {})
            provider_metadata["attempt"] = 1
            print("OpenRouter로 성장 리포트를 처리했습니다.")
            if computed_metrics is not None:
                analysis = _compose_growth_report_from_ai(
                    response_text,
                    character,
                    computed_metrics,
                    growth_insights,
                    analysis_context,
                    source_data,
                    expected_date,
                    "OpenRouter",
                )
            else:
                analysis = sanitize_ai_text(response_text, expected_date)
                if not validate_growth_report(analysis):
                    error = ProviderError(
                        "OpenRouter report format validation failed.",
                        "provider_invalid_output",
                    )
                    error.validation_reason = "report_format"
                    error.provider_metadata = {
                        **provider_metadata,
                        "response_classification": "report_format_failed",
                    }
                    raise error
            generation = _build_generation_metadata(
                "openrouter",
                provider_metadata,
                fallback_used=gemini_error is not None,
                fallback_reason=provider_error_type(gemini_error) if gemini_error is not None else None,
            )
            _store_cached_ai_response(cache_key, analysis, metadata={"generation": generation})
            metadata = _log_provider_success(
                "openrouter",
                provider_metadata,
                validated=True,
                returned=True,
                cache_hit=False,
            )
            return {
                "analysis": analysis,
                "cacheHit": False,
                "growthInsights": growth_insights,
                "aiGenerated": True,
                "aiStatus": "generated",
                "providerMetadata": metadata,
                "generation": generation,
                "delivery": {"source": "generated"},
            }
        except Exception as error:
            _log_provider_failure("openrouter", error, openrouter_started_at, deadline)
            if computed_metrics is not None:
                return _server_fallback_growth_report(
                    character,
                    computed_metrics,
                    growth_insights,
                    analysis_context,
                    provider_error_type(error) or "provider_unavailable",
                )
            return _fallback_failure_result(gemini_error, error)

    if gemini_error:
        if computed_metrics is not None:
            return _server_fallback_growth_report(
                character,
                computed_metrics,
                growth_insights,
                analysis_context,
                provider_error_type(gemini_error),
            )
        return _fallback_failure_result(gemini_error)
    if computed_metrics is not None:
        return _server_fallback_growth_report(
            character, computed_metrics, growth_insights, analysis_context
        )
    return {"error": "AI 분석을 사용할 수 없습니다.", "statusCode": 503, "errorType": "provider_unavailable"}


def _generate_ai_comparison_impl(primary, comparison):
    runtime_state = get_runtime_state()
    gemini_api_key = getattr(runtime_state, "gemini_api_key", "")
    openrouter_api_key = getattr(runtime_state, "openrouter_api_key", "")
    deadline = _request_deadline()
    cooldown_remaining = _gemini_cooldown_remaining(runtime_state) if gemini_api_key else 0.0

    def prepare_subject(subject):
        character = subject["character"]
        metrics = subject["metrics"]
        history = subject.get("history") or []
        return {
            "character": {
                "characterName": character.get("characterName"),
                "worldName": character.get("worldName"),
                "job": character.get("job"),
                "level": character.get("level"),
                "experienceRate": character.get("experienceRate"),
            },
            "metrics": metrics,
            "history": [
                {
                    "date": item.get("date"),
                    "level": item.get("level"),
                    "experienceChange": item.get("experienceChange"),
                    "ranking": item.get("ranking"),
                    "rankingChange": item.get("rankingChange"),
                    "levelUp": item.get("levelUp", False),
                    "recordStatus": item.get("recordStatus"),
                }
                for item in history
            ],
        }

    prompt_data = {"primary": prepare_subject(primary), "comparison": prepare_subject(comparison)}
    prompt = f"""
너는 두 메이플스토리 캐릭터의 성장 차이를 플레이어가 쉽게 이해하도록 설명하는 도우미야.
친근하고 담백한 해요체로 2~4문장만 작성해. 딱딱한 보고서 말투나 AI가 쓴 듯한 상투적인 표현은 피하고, '경험치', '레벨업', '월드 랭킹'처럼 익숙한 메이플 용어를 사용해.
아래 수치는 이미 같은 기준으로 계산되어 있으니 다시 계산하거나 새로운 예측을 만들지 마. 비교 카드에 표시된 숫자와 순위를 반복하기보다, 실제로 확인되는 차이를 쉽게 설명해.
기록이 충분하지 않으면 아직 비교하기 어렵다고 자연스럽게 알려줘. 현재 레벨만으로 우위를 단정하거나 사냥 방식·플레이 시간을 추측하지 마.
개발 용어, 데이터 필드명, 영어 상태값, null, undefined는 본문에 쓰지 마.

비교 데이터:
{json.dumps(prompt_data, ensure_ascii=False)}
"""
    cached_analysis = _get_cached_ai_response(prompt)
    if cached_analysis is not None:
        print("저장된 AI 성장 비교 분석을 재사용했습니다.")
        return {"analysis": cached_analysis, "cacheHit": True}

    gemini_error = None
    if gemini_api_key and cooldown_remaining > 0:
        gemini_error = ProviderError(
            "Gemini quota cooldown is active.",
            "provider_quota",
            retry_after_seconds=max(1, int(cooldown_remaining)),
        )
    elif gemini_api_key:
        gemini_started_at = time.monotonic()
        try:
            response = _generate_gemini_content(prompt, api_key=gemini_api_key, deadline=deadline)
            analysis = sanitize_ai_text(_require_provider_text(getattr(response, "text", None), "Gemini"))
            _clear_gemini_cooldown(runtime_state)
            _store_cached_ai_response(prompt, analysis)
            return {"analysis": analysis, "cacheHit": False}
        except Exception as error:
            gemini_error = error
            if _is_quota_error(error):
                _set_gemini_cooldown(runtime_state, error)
            _log_provider_failure("gemini_comparison", error, gemini_started_at, deadline)
            if not should_use_openrouter(error):
                return _error_result(error, "AI 성장 분석을 불러오지 못했습니다.")

    if openrouter_api_key:
        openrouter_started_at = time.monotonic()
        try:
            response_text = _require_provider_text(
                request_openrouter(prompt, api_key=openrouter_api_key, deadline=deadline),
                "OpenRouter",
            )
            print("OpenRouter로 성장 비교 분석을 처리했습니다.")
            analysis = sanitize_ai_text(response_text)
            _store_cached_ai_response(prompt, analysis)
            return {"analysis": analysis, "cacheHit": False}
        except Exception as error:
            _log_provider_failure("openrouter_comparison", error, openrouter_started_at, deadline)
            return _fallback_failure_result(gemini_error, error)

    if gemini_error:
        return _fallback_failure_result(gemini_error)
    return {"error": "AI 성장 분석을 사용할 수 없습니다.", "statusCode": 503, "errorType": "provider_unavailable"}


# Same-process single-flight for identical AI requests. Completed results continue to
# use the validated response cache above; this registry only shares work while a
# provider request is still in progress.
_AI_INFLIGHT_REQUESTS = {}
_AI_INFLIGHT_LOCK = Lock()


def _ai_singleflight_key(kind, payload):
    runtime_state = get_runtime_state()
    provider_identity = {
        "gemini_key": hashlib.sha256(
            str(getattr(runtime_state, "gemini_api_key", "")).encode("utf-8")
        ).hexdigest(),
        "openrouter_key": hashlib.sha256(
            str(getattr(runtime_state, "openrouter_api_key", "")).encode("utf-8")
        ).hexdigest(),
        "openrouter_model": getattr(runtime_state, "openrouter_model", "openrouter/free"),
    }
    serialized = json.dumps(
        {"kind": kind, "payload": payload, "providers": provider_identity},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _coalesce_ai_operation(kind, payload, operation):
    """동일한 AI 작업의 동시 cache miss를 하나의 공급자 호출로 합친다."""
    request_key = _ai_singleflight_key(kind, payload)
    increment_metric("ai.logical_requests", kind=kind)
    with _AI_INFLIGHT_LOCK:
        future = _AI_INFLIGHT_REQUESTS.get(request_key)
        is_leader = future is None
        if is_leader:
            future = Future()
            _AI_INFLIGHT_REQUESTS[request_key] = future

    if not is_leader:
        increment_metric("ai.coalesced_requests", kind=kind)
        result = future.result()
        if not isinstance(result, dict):
            return result
        shared_result = dict(result)
        if shared_result.get("analysis") is not None:
            shared_result["cacheHit"] = True
            provider_metadata = shared_result.get("providerMetadata")
            if isinstance(provider_metadata, dict):
                provider_metadata = dict(provider_metadata)
                provider_metadata["cache_hit"] = True
                provider_metadata["coalesced"] = True
                shared_result["providerMetadata"] = provider_metadata
        return shared_result

    try:
        result = operation()
    except BaseException as error:
        future.set_exception(error)
        raise
    else:
        future.set_result(result)
        return result
    finally:
        with _AI_INFLIGHT_LOCK:
            if _AI_INFLIGHT_REQUESTS.get(request_key) is future:
                _AI_INFLIGHT_REQUESTS.pop(request_key, None)


def generate_ai_analysis(
    character,
    history,
    computed_metrics=None,
    growth_insights=None,
    analysis_context=None,
    force_refresh=False,
):
    payload = {
        "character": character,
        "history": history,
        "computed_metrics": computed_metrics,
        "growth_insights": growth_insights,
        "analysis_context": analysis_context,
        "force_refresh": force_refresh,
    }
    return _coalesce_ai_operation(
        "growth_report",
        payload,
        lambda: _generate_ai_analysis_impl(
            character,
            history,
            computed_metrics,
            growth_insights,
            analysis_context,
            force_refresh,
        ),
    )


def generate_ai_comparison(primary, comparison):
    return _coalesce_ai_operation(
        "comparison",
        {"primary": primary, "comparison": comparison},
        lambda: _generate_ai_comparison_impl(primary, comparison),
    )
