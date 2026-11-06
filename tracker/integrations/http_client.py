"""외부 HTTP API 공통 요청 정책.

일시적인 네트워크 오류와 제한 응답만 제한적으로 재시도한다.
인증 오류·잘못된 요청 등 재시도해도 해결되지 않는 4xx 응답은 즉시 반환한다.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import time

import requests


RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


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
        if before_attempt:
            before_attempt()

        try:
            response = request_func(url, timeout=timeout, **kwargs)
        except (requests.Timeout, requests.ConnectionError):
            if attempt >= attempts:
                raise
            delay = min(max_backoff, backoff_factor * (2 ** (attempt - 1)))
            if delay > 0:
                time.sleep(delay)
            continue

        if response.status_code not in retry_codes or attempt >= attempts:
            return response

        # 다음 시도 전에 응답 연결을 반환해 연결 풀을 고갈시키지 않는다.
        close_response = getattr(response, "close", None)
        if callable(close_response):
            close_response()

        response_headers = getattr(response, "headers", {}) or {}
        retry_after = _retry_after_seconds(response_headers.get("Retry-After"))
        # Retry-After is an explicit upstream instruction; do not shorten it
        # to max_backoff. The exponential fallback remains bounded.
        delay = (
            retry_after
            if retry_after is not None
            else min(max_backoff, backoff_factor * (2 ** (attempt - 1)))
        )
        if delay > 0:
            time.sleep(delay)

    raise RuntimeError("HTTP 요청 재시도 흐름이 비정상적으로 종료되었습니다.")
