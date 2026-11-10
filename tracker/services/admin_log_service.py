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

class AdminLogService:
    """관리자 로그 기록 유스케이스를 저장소에 위임한다."""

    def __init__(self, repository):
        self.repository = repository

    def initialize(self):
        return self.repository.initialize()

    def connect(self):
        # 기존 테스트와 운영 스크립트의 연결 접근 호환성을 유지한다.
        return self.repository.connect()

    def record_action(
        self,
        action,
        character_name=None,
        world_name=None,
        result="성공",
        comparison_name=None,
        path=None,
        status_code=None,
        duration_ms=None,
        error_type=None,
    ):
        """민감한 요청 본문은 저장하지 않고 운영 메타데이터만 기록한다."""
        import sqlite3
        import time

        import psycopg

        from tracker.services.performance_metrics import increment_metric, observe_metric

        operation_started = time.perf_counter()
        try:
            self.repository.insert(
                action=action,
                character_name=character_name,
                world_name=world_name,
                result=result,
                comparison_name=comparison_name,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                error_type=error_type,
            )
        except (sqlite3.Error, psycopg.Error):
            # DB 비밀번호, API 키, 요청 본문과 같은 상세 정보는 로그에 출력하지 않는다.
            print("관리자 로그 저장에 실패했습니다.")
        finally:
            increment_metric("db.operations", operation="admin_log.insert")
            increment_metric("db.sql_statements", operation="admin_log.insert")
            observe_metric(
                "db.operation_ms",
                (time.perf_counter() - operation_started) * 1000,
                operation="admin_log.insert",
            )

    def list_logs(
        self,
        search_text="",
        selected_action="",
        selected_result="",
        date_from=None,
        date_to=None,
    ):
        """저장소 조회 오류를 화면에서 사용할 안전한 상태로 변환한다."""
        import sqlite3

        import psycopg

        warning = self.repository.state.log_storage_warning
        try:
            result = self.repository.search(
                search_text=search_text,
                selected_action=selected_action,
                selected_result=selected_result,
                date_from=date_from,
                date_to=date_to,
            )
        except (sqlite3.Error, psycopg.Error):
            result = {"rows": [], "total_count": 0, "action_options": []}
            warning = (
                "관리자 로그 저장소에 연결할 수 없습니다. "
                "환경 설정과 데이터베이스 연결을 확인해주세요."
            )
            print("관리자 로그 조회에 실패했습니다.")

        if self.repository.state.log_db_backend == "sqlite" and not warning:
            warning = (
                "현재 로그는 SQLite에 저장됩니다. 개발 환경에는 적합하지만 "
                "Render 재배포 후 보존하려면 PostgreSQL 연결이 필요합니다."
            )

        return {
            **result,
            "storage_warning": warning,
            "storage_backend": self.repository.state.log_db_backend,
        }

