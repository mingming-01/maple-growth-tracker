"""Wall-clock bounded JSON HTTP requests for AI providers."""
import json
import time

import requests


DEFAULT_MAX_RESPONSE_BYTES = 96 * 1024


class InvalidProviderResponse(requests.RequestException):
    """Provider returned a successful HTTP status with an unusable JSON body."""

    error_type = "provider_invalid_response"


class ProviderHTTPPayload(dict):
    """Parsed JSON mapping with safe transport metadata (never request data)."""

    def __init__(
        self, value, *, status_code, elapsed_ms, response_bytes,
        expected_response_bytes=None, body_complete=True, transfer_encoding=None,
        extra_metadata=None,
    ):
        super().__init__(value)
        self.provider_metadata = {
            "http_status": status_code,
            "elapsed_ms": round(elapsed_ms, 1),
            "response_bytes": int(response_bytes),
            "response_body_present": response_bytes > 0,
            "expected_response_bytes": expected_response_bytes,
            "body_complete": bool(body_complete),
            "transfer_encoding": transfer_encoding,
            **(extra_metadata or {}),
        }


def _safe_response_headers(response):
    """Expose only non-sensitive response headers useful for transport diagnosis."""
    headers = getattr(response, "headers", {}) or {}

    def read_header(name, limit):
        value = headers.get(name)
        return str(value)[:limit] if value is not None else None

    request_id = (
        read_header("x-openrouter-request-id", 120)
        or read_header("x-request-id", 120)
        or read_header("request-id", 120)
    )
    return {
        "response_content_type": read_header("Content-Type", 120),
        "response_content_encoding": read_header("Content-Encoding", 80),
        "response_server": read_header("Server", 80),
        "response_request_id": request_id,
    }


def _consume_sse_frame(frame, aggregate):
    normalized = frame.decode("utf-8", errors="replace").replace("\\r\\n", "\\n").replace("\\r", "\\n")
    data_lines = [
        line[5:].lstrip()
        for line in normalized.splitlines()
        if line.startswith("data:")
    ]
    if not data_lines:
        return False
    data = "\n".join(data_lines).strip()
    if data == "[DONE]":
        aggregate["done"] = True
        return True
    try:
        event = json.loads(data)
    except (TypeError, ValueError) as error:
        raise InvalidProviderResponse("OpenRouter stream contained invalid JSON") from error
    if not isinstance(event, dict):
        raise InvalidProviderResponse("OpenRouter stream event was not an object")
    if event.get("error") or event.get("type") == "error":
        raise InvalidProviderResponse("OpenRouter stream returned an error event")
    aggregate["event_count"] += 1
    aggregate["model"] = event.get("model") or aggregate["model"]
    aggregate["provider"] = event.get("provider") or aggregate["provider"]
    if isinstance(event.get("usage"), dict):
        aggregate["usage"] = event["usage"]
    for choice in event.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta") or choice.get("message") or {}
        if isinstance(delta, dict):
            content = delta.get("content")
            if isinstance(content, str):
                aggregate["content"].append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        aggregate["content"].append(part["text"])
            reasoning = delta.get("reasoning") or delta.get("reasoning_content")
            if isinstance(reasoning, str):
                aggregate["reasoning_bytes"] += len(reasoning.encode("utf-8"))
        if choice.get("finish_reason") is not None:
            aggregate["finish_reason"] = choice.get("finish_reason")
        if choice.get("native_finish_reason") is not None:
            aggregate["native_finish_reason"] = choice.get("native_finish_reason")
    return False



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
    response_format="json",
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
    response = None
    body = bytearray()
    body_complete = False
    expected_response_bytes = None
    transfer_encoding = None
    response_header_metadata = {}
    is_sse_response = False
    sse_buffer = bytearray()
    sse = {
        "event_count": 0, "model": None, "provider": None, "usage": {},
        "content": [], "reasoning_bytes": 0, "finish_reason": None,
        "native_finish_reason": None, "done": False,
    }
    local_deadline = started_at + total_timeout
    if deadline is not None:
        local_deadline = min(local_deadline, float(deadline))
    remaining = local_deadline - started_at
    if remaining <= 0:
        raise requests.Timeout("AI provider request deadline has expired")
    if remaining <= 0.1:
        raise requests.Timeout("AI provider request deadline has expired")
    # Requests applies connect and response-header read timeouts consecutively.
    # Keep their combined budget within the remaining wall-clock allowance.
    connect_timeout = min(connect_timeout, max(0.05, remaining * 0.25))
    read_timeout = min(read_timeout, max(0.05, remaining - connect_timeout))

    try:
        response = requests.post(
            url,
            headers=headers,
            json=json_body,
            timeout=(connect_timeout, read_timeout),
            stream=True,
        )
        response_header_metadata = _safe_response_headers(response)
        content_type = str(response_header_metadata.get("response_content_type") or "").lower()
        is_sse_response = (
            response_format == "sse"
            and "text/event-stream" in content_type
            and response.status_code < 400
        )
        try:
            expected_response_bytes = int(response.headers.get("Content-Length"))
        except (AttributeError, TypeError, ValueError):
            expected_response_bytes = None
        transfer_encoding = (
            "chunked" if "chunked" in str(getattr(response, "headers", {}).get("Transfer-Encoding", "")).lower()
            else None
        )
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
                body_complete = True
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
            if is_sse_response:
                sse_buffer.extend(chunk)
                while True:
                    lf_separator = sse_buffer.find(b"\n\n")
                    crlf_separator = sse_buffer.find(b"\r\n\r\n")
                    positions = [p for p in (lf_separator, crlf_separator) if p >= 0]
                    if not positions:
                        break
                    position = min(positions)
                    separator_size = 4 if sse_buffer[position:position + 4] == b"\r\n\r\n" else 2
                    frame = bytes(sse_buffer[:position])
                    del sse_buffer[:position + separator_size]
                    if _consume_sse_frame(frame, sse):
                        body_complete = True
                        break
                if sse["done"]:
                    break

        if time.monotonic() >= local_deadline:
            raise requests.Timeout(
                f"AI provider response exceeded {total_timeout:.1f}s deadline"
            )

        raw_text = body.decode("utf-8-sig", errors="replace")
        if response.status_code >= 400:
            response._content = bytes(body)
            response._content_consumed = True
            error = requests.HTTPError(
                f"{response.status_code} {response.reason}: {raw_text[:2000]}",
                response=response,
            )
            try:
                error_payload = json.loads(raw_text)
                error_object = error_payload.get("error") if isinstance(error_payload, dict) else None
                error_code = error_object.get("code") if isinstance(error_object, dict) else None
            except (TypeError, ValueError):
                error_code = None
            error.provider_metadata = {
                "provider_error_code": str(error_code)[:80] if error_code is not None else None,
                **response_header_metadata,
            }
            raise error

        if is_sse_response:
            if sse_buffer.strip():
                _consume_sse_frame(bytes(sse_buffer), sse)
            if not sse["done"]:
                error = InvalidProviderResponse(
                    "OpenRouter SSE stream ended before its completion marker"
                )
                error.provider_metadata = {
                    **response_header_metadata,
                    "response_classification": "stream_incomplete",
                    "stream_event_count": sse["event_count"],
                    "stream_done": False,
                    "stream_reasoning_bytes": sse["reasoning_bytes"],
                }
                raise error

            event_payload = {
                "model": sse["model"],
                "provider": sse["provider"],
                "usage": sse["usage"],
                "choices": ([{
                    "message": {
                        "content": "".join(sse["content"]),
                        "reasoning_length": sse["reasoning_bytes"],
                    },
                    "finish_reason": sse["finish_reason"],
                    "native_finish_reason": sse["native_finish_reason"],
                }] if sse["event_count"] else []),
            }
            return ProviderHTTPPayload(
                event_payload,
                status_code=response.status_code,
                elapsed_ms=(time.monotonic() - started_at) * 1000,
                response_bytes=len(body),
                expected_response_bytes=expected_response_bytes,
                body_complete=body_complete,
                transfer_encoding=transfer_encoding,
                extra_metadata={
                    **response_header_metadata,
                    "stream_event_count": sse["event_count"],
                    "stream_done": True,
                    "stream_reasoning_bytes": sse["reasoning_bytes"],
                },
            )

        try:
            payload = json.loads(raw_text)
        except (TypeError, ValueError) as error:
            raise InvalidProviderResponse(
                "AI provider returned invalid JSON"
            ) from error
        if not isinstance(payload, dict):
            raise InvalidProviderResponse("AI provider returned an invalid JSON object")
        return ProviderHTTPPayload(
            payload,
            status_code=response.status_code,
            elapsed_ms=(time.monotonic() - started_at) * 1000,
            response_bytes=len(body),
            expected_response_bytes=expected_response_bytes,
            body_complete=True,
            transfer_encoding=transfer_encoding,
            extra_metadata=response_header_metadata,
        )
    except Exception as error:
        existing_metadata = getattr(error, "provider_metadata", None)
        existing_metadata = existing_metadata if isinstance(existing_metadata, dict) else {}
        read_errors = (
            requests.Timeout,
            requests.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ContentDecodingError,
        )
        cause = getattr(error, "__cause__", None)
        context = getattr(error, "__context__", None)
        default_classification = (
            "parse_error" if isinstance(error, InvalidProviderResponse) else
            "response_body_incomplete" if response is not None and isinstance(error, read_errors) else
            "provider_timeout" if isinstance(error, read_errors) else
            "unknown_response_error"
        )
        error.provider_metadata = {
            **existing_metadata,
            "http_status": getattr(response, "status_code", None),
            "elapsed_ms": round((time.monotonic() - started_at) * 1000, 1),
            "response_bytes": len(body),
            "response_body_present": bool(body),
            "expected_response_bytes": expected_response_bytes,
            "body_complete": body_complete,
            "transfer_encoding": transfer_encoding,
            **response_header_metadata,
            "cause_class": type(cause).__name__ if cause is not None else None,
            "context_class": type(context).__name__ if context is not None else None,
            "response_classification": existing_metadata.get("response_classification") or default_classification,
            "timeout_phase": existing_metadata.get("timeout_phase") or (
                "response_body_read" if response is not None and isinstance(error, read_errors) else
                "connect_or_headers" if isinstance(error, read_errors) else None
            ),
        }
        raise
    finally:
        if response is not None:
            response.close()
