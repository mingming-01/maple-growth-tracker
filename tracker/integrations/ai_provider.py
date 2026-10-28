"""AI 제공자(OpenRouter)와 통신한다."""

from app import *


def request_openrouter(prompt):
    if not OPENROUTER_API_KEY:
        return None

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        },
        timeout=60
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
            "TIMEOUT"
        )
    )
