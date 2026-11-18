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

    # Gunicorn 기본 30초 제한 전에 fallback이 끝나도록 연결/읽기 시간을 분리한다.
    # Gemini가 실패한 뒤 실행되는 경로이므로 재시도하지 않고 빠르게 제어를 반환한다.
    timeout = (
        min(3.0, max(0.5, float(_setting("OPENROUTER_CONNECT_TIMEOUT", 2.5)))),
        min(7.0, max(1.0, float(_setting("OPENROUTER_READ_TIMEOUT", 6.5)))),
    )

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
        max_attempts=1,
        backoff_factor=0,
        max_retry_after_wait=0,
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
        )
    )
