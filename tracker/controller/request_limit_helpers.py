"""공개 데이터 API 요청 제한 응답을 공통 형식으로 만든다."""
from flask import jsonify, request

from tracker.services.request_limits import consume_api_request


def api_request_limit_response(force_refresh=False):
    """허용 한도를 넘은 요청에 Retry-After가 포함된 429 응답을 반환한다."""
    allowed, retry_after, reason = consume_api_request(
        request.remote_addr,
        force_refresh=force_refresh,
    )
    if allowed:
        return None

    response = jsonify({
        "error": (
            "요청이 잠시 많습니다. 잠시 후 다시 시도해주세요."
            if reason == "requests_per_minute"
            else "최신 정보 재조회 요청이 잠시 많습니다. 잠시 후 다시 시도해주세요."
        ),
        "limitType": reason,
        "retryAfter": retry_after,
    })
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response
