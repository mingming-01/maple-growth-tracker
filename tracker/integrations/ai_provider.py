"""AI provider adapters with a strict end-to-end response budget."""
import requests

from flask import current_app, has_app_context

from tracker.config import Config
from tracker.integrations.bounded_http import post_json_with_deadline


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _setting(name, default=None):
    if has_app_context():
        return current_app.config.get(name, default)
    return getattr(Config, name, default)


def _provider_timeouts(provider):
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
    return connect_timeout, read_timeout, total_timeout


def _extract_text_parts(parts):
    if not isinstance(parts, list):
        return ""
    return "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()


def request_gemini(prompt, api_key=None):
    """Gemini REST 요청을 한 번 수행하고 응답 전체 시간에 상한을 둔다."""
    key = api_key or _setting("GEMINI_API_KEY", "")
    if not key:
        return None

    model = _setting("GEMINI_MODEL", "gemini-3.6-flash")
    connect_timeout, read_timeout, total_timeout = _provider_timeouts("gemini")
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
    )
    candidates = payload.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        raise requests.RequestException("Gemini 응답에 생성 결과가 없습니다.")
    content = candidates[0].get("content") or {}
    text = _extract_text_parts(content.get("parts"))
    if not text:
        raise requests.RequestException("Gemini 응답에 분석 내용이 없습니다.")
    return text



def _log_openrouter_empty_response(**details):
    """응답 본문/프롬프트/인증정보는 제외하고 제공자 메타데이터만 기록한다."""
    if has_app_context():
        current_app.logger.warning("OpenRouter 텍스트 없는 응답: %s", details)


def request_openrouter(prompt, api_key=None):
    """OpenRouter 대체 호출도 전체 응답 시간을 제한해 worker timeout을 막는다."""
    key = api_key or _setting("OPENROUTER_API_KEY", "")
    if not key:
        return None

    connect_timeout, read_timeout, total_timeout = _provider_timeouts("openrouter")
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
        raise requests.RequestException(
            f"OpenRouter 응답에 choices가 없습니다 (code={error_code!r})."
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
        raise requests.RequestException(
            "OpenRouter 응답에 분석 내용이 없습니다 "
            f"(finish_reason={choice.get('finish_reason')!r})."
        )
    return content.strip()


def should_use_openrouter(error):
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return True
    status_code = getattr(getattr(error, "response", None), "status_code", None)
    if status_code in (408, 425, 429, 500, 502, 503, 504):
        return True
    error_text = str(error).upper()
    return any(
        keyword in error_text
        for keyword in (
            "408",
            "425",
            "429",
            "500",
            "502",
            "503",
            "504",
            "RESOURCE_EXHAUSTED",
            "QUOTA",
            "TIMEOUT",
            "DEADLINE_EXCEEDED",
        )
    )
