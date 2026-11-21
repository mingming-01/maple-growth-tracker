"""Wall-clock bounded JSON HTTP requests for AI providers."""
import json
import time

import requests


DEFAULT_MAX_RESPONSE_BYTES = 96 * 1024
DEFAULT_MAX_SSE_RESPONSE_BYTES = 2 * 1024 * 1024
STREAM_READ_CHUNK_SIZE = 4096


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


def _consume_sse_frame(frame, aggregate, elapsed_ms=None):
    normalized = frame.decode("utf-8", errors="replace").replace("\\r\\n", "\\n").replace("\\r", "\\n")
    data_lines = [
        line[5:].lstrip()
        for line in normalized.splitlines()
        if line.startswith("data:")
    ]
    if not data_lines:
        return False
    data = "\\n".join(data_lines).strip()
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
                if content and aggregate.get("first_content_ms") is None and elapsed_ms is not None:
                    aggregate["first_content_ms"] = round(max(0.0, float(elapsed_ms)), 1)
                aggregate["content"].append(content)
                aggregate["content_bytes"] += len(content.encode("utf-8"))
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        text_part = part["text"]
                        if text_part and aggregate.get("first_content_ms") is None and elapsed_ms is not None:
                            aggregate["first_content_ms"] = round(max(0.0, float(elapsed_ms)), 1)
                        aggregate["content"].append(text_part)
                        aggregate["content_bytes"] += len(text_part.encode("utf-8"))
            reasoning = delta.get("reasoning") or delta.get("reasoning_content")
            if isinstance(reasoning, str):
                if reasoning and aggregate.get("first_reasoning_ms") is None and elapsed_ms is not None:
                    aggregate["first_reasoning_ms"] = round(max(0.0, float(elapsed_ms)), 1)
                aggregate["reasoning_bytes"] += len(reasoning.encode("utf-8"))
        if choice.get("finish_reason") is not None:
            aggregate["finish_reason"] = choice.get("finish_reason")
        if choice.get("native_finish_reason") is not None:
            aggregate["native_finish_reason"] = choice.get("native_finish_reason")
    return False


def _deadline_timeout(message, timeout_cause):
    error = requests.Timeout(message)
    error.provider_metadata = {"timeout_cause": timeout_cause}
    return error


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

    Read bounded chunks instead of one byte at a time. The socket read timeout
    bounds blocking reads, while the wall-clock deadline is checked between chunks.
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
    last_chunk_elapsed_ms = None
    sse = {
        "event_count": 0, "model": None, "provider": None, "usage": {},
        "content": [], "content_bytes": 0, "reasoning_bytes": 0,
        "first_content_ms": None, "first_reasoning_ms": None,
        "finish_reason": None, "native_finish_reason": None, "done": False,
    }
    provider_deadline = started_at + total_timeout
    local_deadline = provider_deadline
    timeout_cause = "provider_attempt_deadline"
    if deadline is not None and float(deadline) <= provider_deadline:
        local_deadline = float(deadline)
        timeout_cause = "request_deadline"
    remaining = local_deadline - started_at
    if remaining <= 0.1:
        raise _deadline_timeout("AI provider request deadline has expired", timeout_cause)
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
        # Some OpenRouter routes can return SSE despite stream=False. In auto mode,
        # use the response Content-Type rather than assuming the request setting won.
        is_sse_response = (
            response_format in {"sse", "auto"}
            and "text/event-stream" in content_type
            and response.status_code < 400
        )
        if is_sse_response:
            # SSE framing/metadata is larger than the compact JSON envelope.
            byte_limit = max(byte_limit, DEFAULT_MAX_SSE_RESPONSE_BYTES)
        try:
            expected_response_bytes = int(response.headers.get("Content-Length"))
        except (AttributeError, TypeError, ValueError):
            expected_response_bytes = None
        transfer_encoding = (
            "chunked" if "chunked" in str(getattr(response, "headers", {}).get("Transfer-Encoding", "")).lower()
            else None
        )
        chunks = iter(response.iter_content(chunk_size=STREAM_READ_CHUNK_SIZE))
        while True:
            remaining = local_deadline - time.monotonic()
            if remaining <= 0:
                raise _deadline_timeout(
                    f"AI provider response exceeded {total_timeout:.1f}s deadline", timeout_cause=timeout_cause
                )
            if not _set_socket_read_timeout(response, min(read_timeout, remaining)):
                error = requests.Timeout("Unable to enforce AI provider response deadline")
                error.provider_metadata = {"timeout_cause": "socket_timeout_enforcement"}
                raise error
            try:
                chunk = next(chunks)
            except StopIteration:
                body_complete = True
                break

            if not chunk:
                continue
            chunk_received_at = time.monotonic()
            last_chunk_elapsed_ms = (chunk_received_at - started_at) * 1000
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
                    if _consume_sse_frame(frame, sse, elapsed_ms=last_chunk_elapsed_ms):
                        body_complete = True
                        break
                if sse["done"] and time.monotonic() < local_deadline:
                    break

            # Process received bytes before enforcing the deadline so diagnostics
            # retain the last complete SSE events, even when the read crossed it.
            if chunk_received_at >= local_deadline:
                raise _deadline_timeout(
                    f"AI provider response exceeded {total_timeout:.1f}s deadline", timeout_cause=timeout_cause
                )

        if time.monotonic() >= local_deadline:
            raise _deadline_timeout(
                f"AI provider response exceeded {total_timeout:.1f}s deadline", timeout_cause=timeout_cause
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
                _consume_sse_frame(bytes(sse_buffer), sse, elapsed_ms=last_chunk_elapsed_ms)
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
                    "stream_first_content_ms": sse["first_content_ms"],
                    "stream_first_reasoning_ms": sse["first_reasoning_ms"],
                    "stream_content_bytes": sse["content_bytes"],
                    "stream_finish_reason": sse["finish_reason"],
                    "stream_native_finish_reason": sse["native_finish_reason"],
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
                    "response_mode": "sse",
                    "stream_event_count": sse["event_count"],
                    "stream_done": True,
                    "stream_reasoning_bytes": sse["reasoning_bytes"],
                    "stream_first_content_ms": sse["first_content_ms"],
                    "stream_first_reasoning_ms": sse["first_reasoning_ms"],
                    "stream_content_bytes": sse["content_bytes"],
                    "stream_finish_reason": sse["finish_reason"],
                    "stream_native_finish_reason": sse["native_finish_reason"],
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
            extra_metadata={**response_header_metadata, "response_mode": "json"},
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
        stream_metadata = {}
        if is_sse_response:
            stream_metadata = {
                "response_mode": "sse",
                "stream_event_count": sse["event_count"],
                "stream_done": sse["done"],
                "stream_content_bytes": sse["content_bytes"],
                "stream_reasoning_bytes": sse["reasoning_bytes"],
                "stream_first_content_ms": sse["first_content_ms"],
                "stream_first_reasoning_ms": sse["first_reasoning_ms"],
                "stream_finish_reason": sse["finish_reason"],
                "stream_native_finish_reason": sse["native_finish_reason"],
            }
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
            **stream_metadata,
            "cause_class": type(cause).__name__ if cause is not None else None,
            "context_class": type(context).__name__ if context is not None else None,
            "response_classification": existing_metadata.get("response_classification") or default_classification,
            "timeout_phase": existing_metadata.get("timeout_phase") or (
                "connect" if isinstance(error, requests.ConnectTimeout) else
                "response_headers" if response is None and isinstance(error, requests.ReadTimeout) else
                "response_body_read" if response is not None and isinstance(error, read_errors) else
                "connect_or_headers" if isinstance(error, read_errors) else None
            ),
        }
        raise
    finally:
        if response is not None:
            response.close()
