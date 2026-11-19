"""AI 성장 분석과 캐릭터 비교의 프롬프트·모델 호출을 담당한다."""
import json
import logging
import re
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import current_app, has_app_context, has_request_context, request
from datetime import date
from types import SimpleNamespace

from tracker.integrations.ai_provider import (
    ProviderError,
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
from tracker.runtime import (
    get_ai_response_cache,
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


def _log_provider_failure(provider, error, started_at, deadline):
    """공급자 실패 원인을 비밀정보 없이 구조화 로그로 기록한다."""
    now = time.monotonic()
    response = getattr(error, "response", None)
    http_status = (
        getattr(error, "status_code", None)
        or getattr(response, "status_code", None)
    )
    response_body = ""
    response_error_code = None
    response_error_message = None
    if response is not None:
        try:
            response_body = response.text or ""
        except Exception:
            response_body = ""
        try:
            response_json = json.loads(response_body) if response_body else {}
        except (TypeError, ValueError):
            response_json = {}
        provider_payload = response_json.get("error") if isinstance(response_json, dict) else None
        if isinstance(provider_payload, dict):
            response_error_code = provider_payload.get("code")
            response_error_message = provider_payload.get("message")
        elif response_body:
            response_error_message = response_body
    safe_message = str(response_error_message or "")[:400]
    # 공급자 오류 메시지에 인증 문자열이 섞이는 경우 로그에 남기지 않는다.
    safe_message = re.sub(r"(?i)bearer\s+[^\s,;]+", "Bearer [REDACTED]", safe_message)
    safe_message = re.sub(
        r"(?i)(api[_-]?key|access[_-]?token|secret|authorization)(\s*[:=]\s*)[^,;\s]+",
        r"\1\2[REDACTED]",
        safe_message,
    )
    details = {
        "provider": provider,
        "error_type": provider_error_type(error),
        "exception_class": type(error).__name__,
        "elapsed_ms": round((now - started_at) * 1000, 1),
        "deadline_remaining_ms": max(0, round((float(deadline) - now) * 1000, 1)),
        "http_status": http_status,
        "provider_error_code": response_error_code,
        "provider_error_message": safe_message or None,
        "finish_reason": getattr(error, "finish_reason", None),
    }
    log_message = json.dumps(details, ensure_ascii=False, sort_keys=True)
    if has_app_context():
        current_app.logger.warning("AI 공급자 요청 실패: %s", log_message)
    else:
        # 서비스 단위 테스트나 Flask 외부 작업에서도 폴백 경로를 중단하지 않는다.
        logging.getLogger(__name__).warning("AI 공급자 요청 실패: %s", log_message)

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


def _store_cached_ai_response(cache_key, analysis):
    """공급자가 만든 정상 분석문을 캐시 저장 실패와 무관하게 반환한다."""
    try:
        set_ai_response_cache(cache_key, analysis)
        return True
    except Exception as error:
        _log_ai_cache_failure("write", error)
        return False


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
    }


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
    return value.strip()



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


def _build_growth_report_prompt(source_data):
    prompt_data = dict(source_data)
    selected_period = prompt_data.get("selectedPeriod") or {}
    period_days = selected_period.get("periodDays", 7)
    if period_days in (30, 90):
        # 장기 리포트에는 7일 기준 평균/증감 지표를 섞지 않는다.
        # 장기 기간 통계는 periodSummary, 전망은 최근 7일 기준 prediction으로 분리한다.
        original_metrics = prompt_data.get("metrics") or {}
        level_progress = original_metrics.get("levelProgress") or {}
        prompt_data["metrics"] = {
            "recentSevenDayPrediction": original_metrics.get("prediction"),
            "currentLevelProgress": {
                key: level_progress.get(key)
                for key in ("currentRate", "remainingRate")
                if key in level_progress
            },
        }
        prompt_data["growthInsights"] = None

    return f"""
너는 메이플스토리 캐릭터의 성장 기록을 읽고 플레이어가 편하게 이해할 수 있는 리포트를 쓰는 도우미야.
친근하고 담백한 해요체를 사용해. 메이플스토리에서 익숙한 경험치, 레벨업, 월드 랭킹 표현을 우선해.

[작성 규칙]
- 아래 분석 자료에 있는 사실만 사용해. 수치·날짜·평균·비율·원인·행동을 새로 계산하거나 추측하지 마.
- 경험치 증가량과 현재 레벨 진행률을 구분해. experienceRate는 현재 레벨 진행률이야. 남은 비율은 currentLevelProgress.remainingRate가 있을 때만 말해.
- 7일 리포트는 growthInsights의 최근/직전 7일 비교를 참고해. 비교할 기록이 부족하면 증가·감소를 단정하지 마.
- 30일·90일 리포트는 selectedPeriod.periodSummary가 선택 기간의 핵심 근거야. metrics의 전망과 진행률은 최근 7일 기준이므로 장기 기간 통계처럼 설명하지 마.
- 예상 레벨업은 metrics.prediction 또는 metrics.recentSevenDayPrediction에 날짜가 있을 때만, 참고값임을 밝혀 말해. 서버가 계산한 정확한 전망 문장도 함께 제공되므로, 그 의미와 전제 조건을 자연스럽게 설명해.
- 기록이 적으면 흐름이 꾸준하다거나 안정적이라고 말하지 마. 근거 없는 칭찬, 사냥 방식, 플레이 시간, 접속 습관을 만들지 마.
- 하루 평균 경험치는 확인된 경험치 변화의 평균으로 설명하고, 큰 경험치는 '17.8조'처럼 한국어 단위로 써. 과학적 표기, 개발 용어, 데이터 필드명, 모델명, API, null, undefined, 영어 상태값은 본문에 쓰지 마.
- '관측 구간', '표본', '결측', '기록 충실도', '유효 구간', '메트릭' 같은 말 대신 '확인된 날짜', '하루 평균 경험치', '지난 기간과 비교'처럼 자연스럽게 표현해.
- [성장 패턴]은 선택 기간의 전체 흐름, [성장 변화]는 확인된 구체적 차이, [레벨업 분석]은 실제 레벨 변화와 현재 진행 상황, [성장 전망]은 주어진 전망, [AI 코멘트]는 유의할 점 한 가지를 설명해.
- 각 항목은 근거가 있는 자연스러운 한국어 1~2문장으로 작성해. 근거가 없으면 짧게 밝혀.
- 아래 다섯 제목을 정확히 한 번씩 순서대로 사용해. 마크다운·목록·표·별도 제목은 쓰지 마.

[분석 자료]
{json.dumps(prompt_data, ensure_ascii=False)}

[성장 패턴]
[성장 변화]
[레벨업 분석]
[성장 전망]
[AI 코멘트]
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
    """같은 정성 신호라도 서로 다른 캐릭터/기록의 결과가 섞이지 않게 한다."""
    return (
        prompt
        + "\n[리포트 형식 버전] 3\n"
        + "[캐시 식별 데이터]\n"
        + json.dumps(source_data, ensure_ascii=False, sort_keys=True)
    )


def _validate_growth_report_facts(report, source_data):
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
            return False

    for token in re.findall(r"(?<![A-Za-z])\d+(?:,\d{3})*(?:\.\d+)?", report):
        normalized = token.replace(",", "")
        try:
            number = format(Decimal(normalized).normalize(), "f")
        except InvalidOperation:
            return False
        if number not in allowed_numbers:
            return False

    for number, unit in re.findall(
        r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(경|조|억|만|%p|%|레벨|회|일|위)",
        report,
    ):
        normalized = format(Decimal(number.replace(",", "")).normalize(), "f")
        if (normalized, unit) not in allowed_number_units:
            return False
    return True


def _build_deterministic_growth_report(character, metrics, growth_insights, analysis_context, ai_comment):
    """수치·날짜·레벨 진행률은 서버 계산값으로만 리포트에 작성한다."""
    metrics = metrics or {}
    insights = growth_insights or {}
    period_days = (analysis_context or {}).get("periodDays", 7)
    recent = insights.get("recentPeriod") if period_days == 7 else None
    previous = insights.get("previousPeriod") if period_days == 7 else None
    summary = recent or metrics.get("periodSummary") or {}

    period_label = _format_period_date_range(
        summary.get("startDate"), summary.get("endDate")
    )
    period_name = "최근 7일" if period_days == 7 else f"선택한 {period_days}일"

    total_text = _format_experience_korean(summary.get("observedExperienceSum"))
    average_text = _format_experience_korean(summary.get("averageDailyExperience"))
    valid_intervals = summary.get("validGrowthIntervals")

    if total_text and average_text and isinstance(valid_intervals, int):
        date_prefix = f"{period_label} 동안 " if period_label else ""
        growth_pattern = (
            f"{date_prefix}확인된 {valid_intervals}회의 일일 경험치 변화 합계는 "
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
    elif average_text:
        growth_change = f"{period_name}의 하루 평균은 {average_text}로 확인됐어요. 비교할 이전 기간의 기록은 충분하지 않아요."
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


def generate_ai_analysis(character, history, computed_metrics=None, growth_insights=None, analysis_context=None, force_refresh=False):
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
            if (
                not _validate_growth_report_facts(cached_analysis, source_data)
                or not validate_growth_report(cached_analysis)
            ):
                cached_analysis = None
        if cached_analysis is not None:
            print("저장된 AI 성장 리포트를 재사용했습니다.")
            return {"analysis": cached_analysis, "cacheHit": True, "growthInsights": growth_insights}

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
            analysis = sanitize_ai_text(gemini_text, expected_date)
            if computed_metrics is not None:
                analysis = _apply_deterministic_growth_forecast(
                    analysis, character, computed_metrics
                )
                if not _validate_growth_report_facts(analysis, source_data):
                    raise ProviderError(
                        "Gemini 분석에 입력 데이터와 일치하지 않는 수치나 날짜가 있습니다.",
                        "provider_invalid_output",
                    )
            if not validate_growth_report(analysis):
                raise ProviderError("Gemini 분석 결과가 리포트 검증을 통과하지 못했습니다.", "provider_invalid_output")
            _clear_gemini_cooldown(runtime_state)
            _store_cached_ai_response(cache_key, analysis)
            return {"analysis": analysis, "cacheHit": False, "growthInsights": growth_insights}
        except Exception as error:
            gemini_error = error
            if _is_quota_error(error):
                delay = _set_gemini_cooldown(runtime_state, error)
                print(f"Gemini 쿼터 제한으로 {delay}초 쿨다운을 적용했습니다.")
            _log_provider_failure("gemini", error, gemini_started_at, deadline)
            if not should_use_openrouter(error):
                return _error_result(error, "AI 분석을 불러오지 못했습니다.")

    if openrouter_api_key:
        openrouter_error = None
        for attempt, reasoning_effort in enumerate(("low", "minimal")):
            openrouter_started_at = time.monotonic()
            try:
                response_text = _require_provider_text(
                    request_openrouter(
                        prompt,
                        api_key=openrouter_api_key,
                        deadline=deadline,
                        reasoning_effort=reasoning_effort,
                    ),
                    "OpenRouter",
                )
                print("OpenRouter로 성장 리포트를 처리했습니다.")
                analysis = sanitize_ai_text(response_text, expected_date)
                if computed_metrics is not None:
                    analysis = _apply_deterministic_growth_forecast(
                        analysis, character, computed_metrics
                    )
                    if not _validate_growth_report_facts(analysis, source_data):
                        raise ProviderError(
                            "OpenRouter 분석에 입력 데이터와 일치하지 않는 수치나 날짜가 있습니다.",
                            "provider_invalid_output",
                        )
                if not validate_growth_report(analysis):
                    raise ProviderError("OpenRouter 분석 결과가 리포트 검증을 통과하지 못했습니다.", "provider_invalid_output")
                _store_cached_ai_response(cache_key, analysis)
                return {"analysis": analysis, "cacheHit": False, "growthInsights": growth_insights}
            except Exception as error:
                openrouter_error = error
                _log_provider_failure("openrouter", error, openrouter_started_at, deadline)
                if attempt == 0 and provider_error_type(error) == "provider_output_truncated":
                    if has_app_context():
                        current_app.logger.warning(
                            "OpenRouter 응답이 출력 한도에 도달해 같은 openrouter/free 경로를 최소 추론 강도로 한 번 재시도합니다."
                        )
                    continue
                break
        return _fallback_failure_result(gemini_error, openrouter_error)

    if gemini_error:
        return _fallback_failure_result(gemini_error)
    return {"error": "AI 분석을 사용할 수 없습니다.", "statusCode": 503, "errorType": "provider_unavailable"}


def generate_ai_comparison(primary, comparison):
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
