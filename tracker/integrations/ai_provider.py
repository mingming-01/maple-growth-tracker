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
    read_timeout = min(
        4.0, max(1.0, float(_setting("AI_PROVIDER_READ_TIMEOUT", 4.0)))
    )
    total_default = 7.0 if provider == "gemini" else 5.0
    total_timeout = min(
        8.0 if provider == "gemini" else 6.0,
        max(1.0, float(_setting(
            "AI_GEMINI_TOTAL_TIMEOUT" if provider == "gemini" else "AI_OPENROUTER_TOTAL_TIMEOUT",
            total_default,
        ))),
    )
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
            "max_tokens": 640,
            "stream": False,
        },
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        total_timeout=total_timeout,
    )
    choices = payload.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise requests.RequestException("OpenRouter 응답에 choices가 없습니다.")

    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        content = _extract_text_parts(content)
    if not isinstance(content, str) or not content.strip():
        raise requests.RequestException("OpenRouter 응답에 분석 내용이 없습니다.")
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
