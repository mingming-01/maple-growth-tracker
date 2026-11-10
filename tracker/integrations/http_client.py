"""외부 HTTP API 공통 요청 정책.

일시적인 네트워크 오류와 제한 응답만 제한적으로 재시도한다.
인증 오류·잘못된 요청 등 재시도해도 해결되지 않는 4xx 응답은 즉시 반환한다.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import time

import requests


# 429 is returned immediately so the API route can serve a saved snapshot.
# Waiting through Retry-After inside a fan-out request can freeze the whole dashboard.
RETRYABLE_STATUS_CODES = {408, 425, 500, 502, 503, 504}
DEFAULT_MAX_RETRY_AFTER_WAIT_SECONDS = 5.0


def _retry_after_seconds(value):
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def request_with_retries(
    method,
    url,
    *,
    timeout,
    max_attempts=2,
    backoff_factor=0.35,
    max_backoff=3.0,
    before_attempt=None,
    retry_status_codes=None,
    max_retry_after_wait=DEFAULT_MAX_RETRY_AFTER_WAIT_SECONDS,
    on_attempt=None,
    on_response=None,
    on_error=None,
    **kwargs,
):
    """요청 실패를 제한적으로 재시도하고, 마지막 응답/예외는 호출자에게 전달한다."""
    method_name = str(method).strip().lower()
    request_func = getattr(requests, method_name, None)
    if request_func is None or not callable(request_func):
        raise ValueError(f"지원하지 않는 HTTP 메서드입니다: {method}")

    attempts = max(1, min(int(max_attempts), 4))
    retry_codes = retry_status_codes or RETRYABLE_STATUS_CODES

    for attempt in range(1, attempts + 1):
        if on_attempt:
            on_attempt(attempt)
        if before_attempt:
            before_attempt()

        attempt_started = time.perf_counter()
        try:
            response = request_func(url, timeout=timeout, **kwargs)
        except (requests.Timeout, requests.ConnectionError) as error:
            if on_error:
                on_error(attempt, error, (time.perf_counter() - attempt_started) * 1000)
            if attempt >= attempts:
                raise
            delay = min(max_backoff, backoff_factor * (2 ** (attempt - 1)))
            if delay > 0:
                time.sleep(delay)
            continue

        if on_response:
            on_response(
                attempt,
                response,
                (time.perf_counter() - attempt_started) * 1000,
            )
        if response.status_code not in retry_codes or attempt >= attempts:
            return response

        response_headers = getattr(response, "headers", {}) or {}
        retry_after = _retry_after_seconds(response_headers.get("Retry-After"))
        try:
            retry_after_cap = max(0.0, float(max_retry_after_wait))
        except (TypeError, ValueError):
            retry_after_cap = DEFAULT_MAX_RETRY_AFTER_WAIT_SECONDS

        # upstream 대기 지시가 너무 길면 더 일찍 재시도하지 않고 현재 응답을 돌려준다.
        if retry_after is not None and retry_after > retry_after_cap:
            return response

        # 실제 재시도하기로 한 경우에만 응답 연결을 반환한다.
        close_response = getattr(response, "close", None)
        if callable(close_response):
            close_response()

        delay = (
            retry_after
            if retry_after is not None
            else min(max_backoff, backoff_factor * (2 ** (attempt - 1)))
        )
        if delay > 0:
            time.sleep(delay)

    raise RuntimeError("HTTP 요청 재시도 흐름이 비정상적으로 종료되었습니다.")
