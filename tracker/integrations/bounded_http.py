"""Wall-clock bounded JSON HTTP requests for AI providers."""
import json
import time

import requests


DEFAULT_MAX_RESPONSE_BYTES = 96 * 1024



def _set_socket_read_timeout(response, timeout):
    """각 socket read의 timeout을 남은 전체 예산으로 줄인다."""
    try:
        sock = response.raw._fp.fp.raw._sock
        sock.settimeout(max(0.05, float(timeout)))
    except (AttributeError, OSError, TypeError, ValueError):
        # 소켓 제한을 적용할 수 없으면 전체 deadline을 보장할 수 없으므로 요청을 실패 처리한다.
        return False
    return True


def post_json_with_deadline(
    url,
    *,
    headers,
    json_body,
    connect_timeout=1.5,
    read_timeout=4.0,
    total_timeout=8.0,
    max_response_bytes=DEFAULT_MAX_RESPONSE_BYTES,
    deadline=None,
):
    """POST JSON with a total deadline, not only Requests' per-read timeout.

    Streaming with one-byte chunks makes the deadline observable even when an
    upstream keeps a chunked response alive by sending tiny pieces periodically.
    The socket read timeout bounds the maximum delay before the next deadline check.
    """
    total_timeout = max(0.5, float(total_timeout))
    connect_timeout = max(0.2, min(float(connect_timeout), total_timeout))
    read_timeout = max(0.2, min(float(read_timeout), total_timeout))
    byte_limit = max(1024, int(max_response_bytes))
    started_at = time.monotonic()
    local_deadline = started_at + total_timeout
    if deadline is not None:
        local_deadline = min(local_deadline, float(deadline))
    remaining = local_deadline - started_at
    if remaining <= 0:
        raise requests.Timeout("AI provider request deadline has expired")
    connect_timeout = min(connect_timeout, remaining)
    read_timeout = min(read_timeout, remaining)

    response = requests.post(
        url,
        headers=headers,
        json=json_body,
        timeout=(connect_timeout, read_timeout),
        stream=True,
    )
    try:
        body = bytearray()
        chunks = iter(response.iter_content(chunk_size=1))
        while True:
            remaining = local_deadline - time.monotonic()
            if remaining <= 0:
                raise requests.Timeout(
                    f"AI provider response exceeded {total_timeout:.1f}s deadline"
                )
            if not _set_socket_read_timeout(response, min(read_timeout, remaining)):
                raise requests.Timeout("Unable to enforce AI provider response deadline")
            try:
                chunk = next(chunks)
            except StopIteration:
                break

            if time.monotonic() >= local_deadline:
                raise requests.Timeout(
                    f"AI provider response exceeded {total_timeout:.1f}s deadline"
                )
            if not chunk:
                continue
            body.extend(chunk)
            if len(body) > byte_limit:
                raise requests.RequestException(
                    f"AI provider response exceeded {byte_limit} byte limit"
                )

        if time.monotonic() >= local_deadline:
            raise requests.Timeout(
                f"AI provider response exceeded {total_timeout:.1f}s deadline"
            )

        raw_text = body.decode("utf-8-sig", errors="replace")
        if response.status_code >= 400:
            response._content = bytes(body)
            response._content_consumed = True
            raise requests.HTTPError(
                f"{response.status_code} {response.reason}: {raw_text[:2000]}",
                response=response,
            )

        try:
            payload = json.loads(raw_text)
        except (TypeError, ValueError) as error:
            raise requests.RequestException(
                "AI provider returned invalid JSON"
            ) from error
        if not isinstance(payload, dict):
            raise requests.RequestException("AI provider returned an invalid JSON object")
        return payload
    finally:
        response.close()
