"""관리자 인증 및 로그 표시에서 재사용하는 HTTP 보조 기능."""
from datetime import datetime
from functools import wraps
from zoneinfo import ZoneInfo
from flask import redirect, session, url_for

KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin.admin_login"))
        return view(*args, **kwargs)
    return wrapped_view


def format_admin_log_time(value):
    """관리자 로그 시간을 한국 시간 기준으로 읽기 쉬운 문자열로 만든다."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if not isinstance(value, datetime):
        return str(value or "-")
    if value.tzinfo is None:
        value = value.replace(tzinfo=KOREA_TIMEZONE)
    else:
        value = value.astimezone(KOREA_TIMEZONE)
    weekdays = ("월", "화", "수", "목", "금", "토", "일")
    return f"{value:%Y-%m-%d} ({weekdays[value.weekday()]}) {value:%H:%M:%S} KST"
