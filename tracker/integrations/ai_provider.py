"""AI 제공자(OpenRouter)와 통신한다."""
import requests

from flask import current_app, has_app_context

from tracker.config import Config
from tracker.integrations.http_client import request_with_retries

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _setting(name, default=None):
    if has_app_context():
        return current_app.config.get(name, default)
    return getattr(Config, name, default)


def request_openrouter(prompt):
    api_key = _setting("OPENROUTER_API_KEY", "")
    if not api_key:
        return None

    timeout = _setting("AI_API_TIMEOUT", 30)
    retries = _setting("AI_API_RETRIES", 1)
    backoff = _setting("AI_API_RETRY_BACKOFF", 0.5)
    try:
        retries = int(retries)
    except (TypeError, ValueError):
        retries = 1
    try:
        backoff = float(backoff)
    except (TypeError, ValueError):
        backoff = 0.5

    response = request_with_retries(
        "post",
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": _setting("OPENROUTER_MODEL", "openrouter/free"),
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
        max_attempts=max(1, retries + 1),
        backoff_factor=max(0.0, backoff),
    )
    response.raise_for_status()

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise ValueError("OpenRouter 응답에 choices가 없습니다.")

    message = choices[0].get("message", {})
    content = message.get("content")
    if not content:
        raise ValueError("OpenRouter 응답에 분석 내용이 없습니다.")

    return content


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
            "429",
            "RESOURCE_EXHAUSTED",
            "QUOTA",
            "503",
            "504",
            "TIMEOUT",
        )
    )
