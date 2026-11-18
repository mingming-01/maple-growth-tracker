"""AI provider adapters with a strict end-to-end response budget."""
import re
import time
import requests

from flask import current_app, has_app_context

from tracker.config import Config
from tracker.integrations.bounded_http import post_json_with_deadline


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class ProviderError(requests.RequestException):
    """Structured provider failure safe to classify across service layers."""

    def __init__(self, message, error_type, status_code=None, retry_after_seconds=None):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


def provider_error_type(error):
    explicit = getattr(error, "error_type", None)
    if explicit:
        return explicit
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None) or getattr(error, "status_code", None)
    if status == 429:
        return "provider_quota"
    if status in (408, 425) or isinstance(error, requests.Timeout):
        return "provider_timeout"
    if status in (500, 502, 503, 504) or isinstance(error, requests.ConnectionError):
        return "provider_unavailable"
    return "provider_error"


def provider_retry_after_seconds(error, default_seconds=300):
    explicit = getattr(error, "retry_after_seconds", None)
    if explicit:
        return max(1, min(86400, int(explicit)))
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {}) or {}
    retry_after = headers.get("Retry-After") if hasattr(headers, "get") else None
    if retry_after:
        try:
            return max(1, min(86400, int(float(retry_after))))
        except (TypeError, ValueError):
            pass
    body = ""
    if response is not None:
        try:
            body = response.text or ""
        except Exception:
            body = ""
    match = re.search(r"retryDelay['\\"]?\\s*:\\s*['\\"]?(\\d+(?:\\.\\d+)?)s", body or str(error), re.I)
    if match:
        return max(1, min(86400, int(float(match.group(1)))))
    return max(1, min(86400, int(default_seconds)))


def _setting(name, default=None):
    if has_app_context():
        return current_app.config.get(name, default)
    return getattr(Config, name, default)


def _provider_timeouts(provider, deadline=None):
    connect_timeout = min(
        2.0, max(0.5, float(_setting("AI_PROVIDER_CONNECT_TIMEOUT", 1.5)))
    )
    if provider == "gemini":
        read_timeout = min(
            5.5, max(2.0, float(_setting("AI_GEMINI_READ_TIMEOUT", 5.0)))
        )
        total_timeout = min(
            8.0,
            max(1.0, float(_setting("AI_GEMINI_TOTAL_TIMEOUT", 7.0))),
        )
    else:
        # Free routed models commonly need longer to start and complete generation.
        # Keep this bounded below Gunicorn's 30s worker timeout after Gemini fallback.
        read_timeout = min(
            17.0, max(3.0, float(_setting("AI_OPENROUTER_READ_TIMEOUT", 16.5)))
        )
        total_timeout = min(
            18.0,
            max(2.0, float(_setting("AI_OPENROUTER_TOTAL_TIMEOUT", 18.0))),
        )
    read_timeout = min(read_timeout, max(0.5, total_timeout - connect_timeout))
    if deadline is not None:
        remaining = float(deadline) - time.monotonic()
        if remaining <= 0:
            raise requests.Timeout("AI provider request deadline has expired")
        total_timeout = min(total_timeout, remaining)
        connect_timeout = min(connect_timeout, total_timeout)
        read_timeout = min(read_timeout, total_timeout)
    return connect_timeout, read_timeout, total_timeout


def _extract_text_parts(parts):
    if not isinstance(parts, list):
        return ""
    return "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()


def request_gemini(prompt, api_key=None, deadline=None)
    """Gemini REST 요청을 한 번 수행하고 응답 전체 시간에 상한을 둔다."""
    key = api_key or _setting("GEMINI_API_KEY", "")
    if not key:
        return None

    model = _setting("GEMINI_MODEL", "gemini-3.6-flash")
    connect_timeout, read_timeout, total_timeout = _provider_timeouts("gemini", deadline=deadline)
    payload = post_json_with_deadline(
        GEMINI_URL.format(model=model),
        headers={
            "x-goog-api-key": key,
            "Content-Type": "application/json",
        },
        json_body={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": 640,
            },
        },
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        total_timeout=total_timeout,
        deadline=deadline,
    )
    candidates = payload.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        raise ProviderError("Gemini 응답에 생성 결과가 없습니다.", "provider_empty_response")
    content = candidates[0].get("content") or {}
    text = _extract_text_parts(content.get("parts"))
    if not text:
        raise ProviderError("Gemini 응답에 분석 내용이 없습니다.", "provider_empty_response")
    return text



def _log_openrouter_empty_response(**details):
    """응답 본문/프롬프트/인증정보는 제외하고 제공자 메타데이터만 기록한다."""
    if has_app_context():
        current_app.logger.warning("OpenRouter 텍스트 없는 응답: %s", details)


def request_openrouter(prompt, api_key=None, deadline=None)
    """OpenRouter 대체 호출도 전체 응답 시간을 제한해 worker timeout을 막는다."""
    key = api_key or _setting("OPENROUTER_API_KEY", "")
    if not key:
        return None

    connect_timeout, read_timeout, total_timeout = _provider_timeouts("openrouter", deadline=deadline)
    payload = post_json_with_deadline(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json_body={
            "model": _setting("OPENROUTER_MODEL", "openrouter/free"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.35,
            "max_tokens": 4096,
            # openrouter/free may route to reasoning models; cap internal reasoning
            # so the limited completion budget is not consumed before final content.
            "reasoning": {"effort": "low"},
            "stream": False,
        },
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        total_timeout=total_timeout,
        deadline=deadline,
    )
    choices = payload.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        provider_error = payload.get("error")
        error_code = None
        error_message = None
        if isinstance(provider_error, dict):
            error_code = provider_error.get("code")
            error_message = provider_error.get("message")
        _log_openrouter_empty_response(
            model=_setting("OPENROUTER_MODEL", "openrouter/free"),
            payload_keys=sorted(payload.keys()),
            error_code=error_code,
            error_message=error_message,
        )
        raise ProviderError(
            f"OpenRouter 응답에 choices가 없습니다 (code={error_code!r}).",
            "provider_invalid_response",
        )

    choice = choices[0]
    message = choice.get("message") or {}
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        content = _extract_text_parts(content)
    if not isinstance(content, str) or not content.strip():
        # Provider metadata only: never log prompts, API keys, or model output.
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        safe_usage = {
            key: usage.get(key)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens")
            if isinstance(usage.get(key), (int, float))
        }
        reasoning = message.get("reasoning") if isinstance(message, dict) else None
        _log_openrouter_empty_response(
            requested_model=_setting("OPENROUTER_MODEL", "openrouter/free"),
            selected_model=payload.get("model"),
            provider=payload.get("provider") if isinstance(payload.get("provider"), str) else None,
            payload_keys=sorted(payload.keys()),
            choice_keys=sorted(choice.keys()),
            finish_reason=choice.get("finish_reason"),
            native_finish_reason=choice.get("native_finish_reason"),
            message_keys=sorted(message.keys()) if isinstance(message, dict) else [],
            content_type=type(content).__name__,
            content_length=len(content) if isinstance(content, str) else None,
            reasoning_type=type(reasoning).__name__,
            reasoning_length=len(reasoning) if isinstance(reasoning, str) else None,
            usage=safe_usage,
            refusal_present=bool(message.get("refusal")) if isinstance(message, dict) else False,
        )
        error_type = "provider_output_truncated" if choice.get("finish_reason") == "length" else "provider_empty_response"
        raise ProviderError(
            "OpenRouter 응답에 최종 분석 내용이 없습니다 "
            f"(finish_reason={choice.get('finish_reason')!r}).",
            error_type,
        )
    if choice.get("finish_reason") == "length":
        raise ProviderError("OpenRouter 응답이 출력 길이 제한으로 잘렸습니다.", "provider_output_truncated")
    if has_app_context():
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        current_app.logger.info("OpenRouter 분석 응답 메타데이터: %s", {
            "requested_model": _setting("OPENROUTER_MODEL", "openrouter/free"),
            "selected_model": payload.get("model"),
            "provider": payload.get("provider"),
            "finish_reason": choice.get("finish_reason"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        })
    return content.strip()


def should_use_openrouter(error):
    if provider_error_type(error) in {
        "provider_timeout", "provider_unavailable", "provider_quota",
        "provider_empty_response", "provider_invalid_response",
        "provider_output_truncated", "provider_invalid_output",
    }:
        return True
    status_code = getattr(getattr(error, "response", None), "status_code", None)
    if status_code in (408, 425, 429, 500, 502, 503, 504):
        return True
    error_text = str(error).upper()
    return any(keyword in error_text for keyword in ("RESOURCE_EXHAUSTED", "QUOTA", "DEADLINE_EXCEEDED"))
