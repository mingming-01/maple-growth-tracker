"""AI 제공자(OpenRouter)와 통신한다."""
import requests
from flask import current_app, has_app_context

from tracker.config import Config

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _setting(name, default=None):
    if has_app_context():
        return current_app.config.get(name, default)
    return getattr(Config, name, default)


def request_openrouter(prompt):
    api_key = _setting("OPENROUTER_API_KEY", "")
    if not api_key:
        return None

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": _setting("OPENROUTER_MODEL", "openrouter/free"),
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
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
