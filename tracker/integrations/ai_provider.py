"""AI provider adapters with a strict end-to-end response budget."""
import re
import time
from email.utils import parsedate_to_datetime
import requests

from flask import current_app, has_app_context

from tracker.config import Config
from tracker.integrations.bounded_http import post_json_with_deadline


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class ProviderError(requests.RequestException):
    """Structured provider failure safe to classify across service layers."""

    def __init__(
        self, message, error_type, status_code=None, retry_after_seconds=None,
        finish_reason=None, provider_metadata=None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.finish_reason = finish_reason
        self.provider_metadata = provider_metadata or {}


class ProviderText(str):
    """Text-compatible provider result carrying non-sensitive response metadata."""

    def __new__(cls, value, provider_metadata=None):
        result = super().__new__(cls, value)
        result.provider_metadata = provider_metadata or {}
        return result


def provider_error_type(error):
    explicit = getattr(error, "error_type", None)
    if explicit:
        if explicit == "provider_invalid_response":
            metadata = getattr(error, "provider_metadata", None) or getattr(error, "http_metadata", None)
            return "provider_parse_error" if isinstance(metadata, dict) and metadata.get("response_classification") == "parse_error" else explicit
        return explicit
    metadata = getattr(error, "provider_metadata", None) or getattr(error, "http_metadata", None)
    if isinstance(metadata, dict) and metadata.get("response_classification") in {
        "provider_timeout", "response_body_incomplete"
    }:
        return "provider_timeout"
    if any(token in str(error).upper() for token in ("RESOURCE_EXHAUSTED", "QUOTA")):
        return "provider_quota"
    response = getattr(error, "response", None)
    status = (getattr(response, "status_code", None) or getattr(error, "status_code", None) or getattr(error, "code", None))
    if status == 429:
        return "provider_quota"
    if status in (401, 403):
        return "provider_auth"
    if status == 402:
        return "provider_billing"
    if status == 400:
        return "provider_bad_request"
    if status == 404:
        return "provider_model_unavailable"
    if status == 413:
        return "provider_payload_too_large"
    error_text = str(error).upper()
    if status in (408, 425) or isinstance(error, requests.Timeout) or any(
        marker in error_text for marker in ("READ TIMED OUT", "CONNECT TIMED OUT", "DEADLINE")
    ):
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
            try:
                return max(1, min(86400, int(parsedate_to_datetime(retry_after).timestamp() - time.time())))
            except (TypeError, ValueError, OverflowError):
                pass
    body = ""
    if response is not None:
        try:
            body = response.text or ""
        except Exception:
            body = ""
    match = re.search(r"retryDelay.{0,12}?(\d+(?:\.\d+)?)s", body or str(error), re.I)
    if match:
        return max(1, min(86400, int(float(match.group(1)))))
    return max(1, min(86400, int(default_seconds)))


def _setting(name, default=None):
    if has_app_context():
        return current_app.config.get(name, default)
    return getattr(Config, name, default)


def _provider_timeouts(provider, deadline=None):
    connect_timeout = min(
        2.0, max(0.5, float(_setting("AI_PROVIDER_CONNECT_TIMEOUT", 2.0)))
    )
    if provider == "gemini":
        read_timeout = min(
            22.0, max(2.0, float(_setting("AI_GEMINI_READ_TIMEOUT", 22.0)))
        )
        total_timeout = min(
            24.0,
            max(1.0, float(_setting("AI_GEMINI_TOTAL_TIMEOUT", 24.0))),
        )
    else:
        read_timeout = min(
            33.0, max(3.0, float(_setting("AI_OPENROUTER_READ_TIMEOUT", 33.0)))
        )
        total_timeout = min(
            35.0,
            max(2.0, float(_setting("AI_OPENROUTER_TOTAL_TIMEOUT", 35.0))),
        )
    read_timeout = min(read_timeout, max(0.5, total_timeout - connect_timeout))
    if deadline is not None:
        remaining = float(deadline) - time.monotonic()
        if provider == "gemini" and _setting("OPENROUTER_API_KEY", ""):
            reserve = max(
                1.0,
                float(_setting("AI_OPENROUTER_MIN_REMAINING_SECONDS", 15.0)),
            )
            remaining -= reserve
        if remaining <= 0:
            raise requests.Timeout("AI provider deadline leaves no execution budget")
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


def _safe_usage(usage):
    if not isinstance(usage, dict):
        return {}
    safe_fields = {
        "prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens",
        "promptTokenCount", "candidatesTokenCount", "totalTokenCount", "thoughtsTokenCount",
    }
    return {
        str(key): value
        for key, value in usage.items()
        if key in safe_fields and isinstance(value, (int, float)) and not isinstance(value, bool)
    }


def _http_metadata(payload, provider, model_alias):
    metadata = dict(getattr(payload, "provider_metadata", {}) or {})
    metadata.update({
        "provider": provider,
        "model_alias": model_alias,
        "selected_model": payload.get("modelVersion") or payload.get("model"),
    })
    return metadata


def request_gemini(prompt, api_key=None, deadline=None):
    """Send one bounded Gemini request and preserve safe response metadata."""
    key = api_key or _setting("GEMINI_API_KEY", "")
    if not key:
        return None

    model = _setting("GEMINI_MODEL", "gemini-3.6-flash")
    connect_timeout, read_timeout, total_timeout = _provider_timeouts("gemini", deadline=deadline)
    payload = post_json_with_deadline(
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json_body={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.35, "maxOutputTokens": 2048},
        },
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        total_timeout=total_timeout,
        deadline=deadline,
    )
    metadata = _http_metadata(payload, "gemini", model)
    metadata["usage"] = _safe_usage(payload.get("usageMetadata"))
    candidates = payload.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        metadata.update({"candidate_count": len(candidates), "response_classification": "empty_content"})
        raise ProviderError("Gemini returned no candidate", "provider_empty_response", provider_metadata=metadata)
    candidate = candidates[0]
    finish_reason = candidate.get("finishReason")
    metadata.update({"candidate_count": len(candidates), "finish_reason": finish_reason})
    if finish_reason == "MAX_TOKENS":
        metadata["response_classification"] = "truncated_output"
        raise ProviderError("Gemini output was truncated", "provider_output_truncated", finish_reason=finish_reason, provider_metadata=metadata)
    if finish_reason in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"}:
        metadata["response_classification"] = "provider_rejected"
        raise ProviderError("Gemini rejected the response", "provider_rejected", finish_reason=finish_reason, provider_metadata=metadata)
    content = candidate.get("content") or {}
    parts = content.get("parts") or []
    text = _extract_text_parts(parts)
    if not text:
        metadata.update({
            "response_classification": "reasoning_only" if any(
                isinstance(part, dict) and part.get("thought") is True for part in parts
            ) or bool((payload.get("usageMetadata") or {}).get("thoughtsTokenCount")) else "empty_content",
            "content_present": False,
        })
        raise ProviderError("Gemini response contained no report text", "provider_empty_response", finish_reason=finish_reason, provider_metadata=metadata)
    metadata.update({"content_present": True, "response_classification": "content_present"})
    return ProviderText(text, metadata)


def _log_openrouter_empty_response(**details):
    """응답 본문/프롬프트/인증정보는 제외하고 제공자 메타데이터만 기록한다."""
    if has_app_context():
        current_app.logger.warning("OpenRouter 텍스트 없는 응답: %s", details)


def request_openrouter(prompt, api_key=None, deadline=None):
    """OpenRouter에 제한된 SSE 요청을 보내고 완료된 텍스트만 반환한다."""
    key = api_key or _setting("OPENROUTER_API_KEY", "")
    if not key:
        return None

    model_alias = _setting("OPENROUTER_MODEL", "openrouter/free")
    connect_timeout, read_timeout, total_timeout = _provider_timeouts(
        "openrouter", deadline=deadline
    )
    payload = post_json_with_deadline(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        json_body={
            "model": model_alias,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.35,
            "max_tokens": max(
                128,
                min(4096, int(_setting("AI_OPENROUTER_MAX_OUTPUT_TOKENS", 4096))),
            ),
            "stream": True,
        },
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        total_timeout=total_timeout,
        deadline=deadline,
        response_format="sse",
    )
    metadata = _http_metadata(payload, "openrouter", model_alias)
    metadata.update({
        "selected_provider": payload.get("provider") if isinstance(payload.get("provider"), str) else None,
        "usage": _safe_usage(payload.get("usage")),
    })
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        metadata.update({
            "has_choices": isinstance(choices, list) and bool(choices),
            "response_classification": "unknown_response_error",
        })
        _log_openrouter_empty_response(**metadata)
        raise ProviderError(
            "OpenRouter returned no usable choice",
            "provider_invalid_response",
            provider_metadata=metadata,
        )

    choice = choices[0]
    message = choice.get("message")
    message = message if isinstance(message, dict) else {}
    raw_content = message.get("content")
    content = _extract_text_parts(raw_content) if isinstance(raw_content, list) else raw_content
    finish_reason = choice.get("finish_reason") or choice.get("native_finish_reason")
    reasoning = message.get("reasoning") or message.get("reasoning_content")
    stream_reasoning_bytes = metadata.get("stream_reasoning_bytes")
    metadata.update({
        "has_choices": True,
        "choice_count": len(choices),
        "has_message": bool(message),
        "content_present": isinstance(content, str) and bool(content.strip()),
        "content_length": len(content) if isinstance(content, str) else 0,
        "content_type": type(raw_content).__name__,
        "finish_reason": finish_reason,
        "native_finish_reason": choice.get("native_finish_reason"),
        "reasoning_present": bool(reasoning) or bool(stream_reasoning_bytes),
        "reasoning_length": (
            len(reasoning) if isinstance(reasoning, str)
            else stream_reasoning_bytes if isinstance(stream_reasoning_bytes, int)
            else None
        ),
    })
    if finish_reason == "length":
        metadata["response_classification"] = "truncated_output"
        _log_openrouter_empty_response(**metadata)
        raise ProviderError(
            "OpenRouter output reached its completion limit",
            "provider_output_truncated",
            finish_reason=finish_reason,
            provider_metadata=metadata,
        )
    if not isinstance(content, str) or not content.strip():
        metadata["response_classification"] = "reasoning_only" if reasoning else "empty_content"
        _log_openrouter_empty_response(**metadata)
        raise ProviderError(
            "OpenRouter response contained no report text",
            "provider_empty_response",
            finish_reason=finish_reason,
            provider_metadata=metadata,
        )
    return ProviderText(content.strip(), metadata)


def should_use_openrouter(error):
    if provider_error_type(error) in {
        "provider_timeout", "provider_unavailable", "provider_quota",
        "provider_empty_response", "provider_invalid_response", "provider_parse_error",
        "provider_output_truncated", "provider_invalid_output",
    }:
        return True
    status_code = getattr(getattr(error, "response", None), "status_code", None)
    if status_code in (408, 425, 429, 500, 502, 503, 504):
        return True
    error_text = str(error).upper()
    return any(keyword in error_text for keyword in ("RESOURCE_EXHAUSTED", "QUOTA", "DEADLINE_EXCEEDED"))
