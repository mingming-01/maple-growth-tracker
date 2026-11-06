"""관리자 인증과 운영 로그 HTTP 라우트."""
from datetime import date, datetime, timedelta
import hmac
import secrets
import sqlite3

import psycopg
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from tracker.runtime import (
    KOREA_TIMEZONE,
    admin_required,
    connect_log_db,
    format_admin_log_time,
    get_runtime_state,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    """관리자 계정을 확인하고 인증 세션을 발급한다."""
    admin_username = current_app.config.get("ADMIN_USERNAME", "")
    admin_password_hash = current_app.config.get("ADMIN_PASSWORD_HASH", "")
    admin_password = current_app.config.get("ADMIN_PASSWORD", "")
    if session.get("admin_authenticated"):
        return redirect(url_for("admin.admin_logs"))

    csrf_token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    error = None
    if request.method == "POST":
        submitted_token = request.form.get("csrf_token", "")
        valid_token = hmac.compare_digest(str(csrf_token), str(submitted_token))
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        password_valid = False
        if admin_password_hash:
            try:
                password_valid = check_password_hash(admin_password_hash, password)
            except (ValueError, TypeError):
                password_valid = False
        elif admin_password:
            password_valid = hmac.compare_digest(admin_password, password)

        if not admin_username or not (admin_password_hash or admin_password):
            error = "관리자 인증 환경변수가 설정되지 않았습니다."
        elif valid_token and hmac.compare_digest(admin_username, username) and password_valid:
            session.clear()
            session["admin_authenticated"] = True
            session["csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("admin.admin_logs"))
        else:
            error = "아이디 또는 비밀번호를 확인해주세요."

    return render_template(
        "admin_login.html",
        csrf_token=csrf_token,
        error=error,
        configured=bool(admin_username and (admin_password_hash or admin_password))
    )

@admin_bp.route("/logs")
@admin_required
def admin_logs():
    """검색 조건을 적용해 관리자 운영 로그를 시간 역순으로 표시한다."""
    state = get_runtime_state()
    log_db_backend = state.log_db_backend
    search_text = request.args.get("q", "").strip()[:100]
    selected_action = request.args.get("action", "").strip()[:80]
    selected_result = request.args.get("result", "").strip()
    date_from_text = request.args.get("date_from", "").strip()
    date_to_text = request.args.get("date_to", "").strip()

    try:
        date_from = date.fromisoformat(date_from_text) if date_from_text else None
    except ValueError:
        date_from = None
        date_from_text = ""
    try:
        date_to = date.fromisoformat(date_to_text) if date_to_text else None
    except ValueError:
        date_to = None
        date_to_text = ""

    placeholder = "%s" if log_db_backend == "postgres" else "?"
    conditions = []
    parameters = []

    if search_text:
        pattern = f"%{search_text}%"
        conditions.append(
            "("
            "COALESCE(action, '') LIKE " + placeholder
            + " OR COALESCE(path, '') LIKE " + placeholder
            + " OR COALESCE(character_name, '') LIKE " + placeholder
            + " OR COALESCE(world_name, '') LIKE " + placeholder
            + " OR COALESCE(comparison_name, '') LIKE " + placeholder
            + " OR COALESCE(error_type, '') LIKE " + placeholder
            + " OR COALESCE(CAST(status_code AS TEXT), '') LIKE " + placeholder
            + ")"
        )
        parameters.extend([pattern] * 7)

    if selected_action:
        conditions.append(f"action = {placeholder}")
        parameters.append(selected_action)
    if selected_result in ("성공", "실패"):
        conditions.append(f"result = {placeholder}")
        parameters.append(selected_result)
    else:
        selected_result = ""

    def date_bound(day):
        value = datetime.combine(day, datetime.min.time()).replace(tzinfo=KOREA_TIMEZONE)
        return value if LOG_DB_BACKEND == "postgres" else value.isoformat(timespec="seconds")

    if date_from:
        conditions.append(f"created_at >= {placeholder}")
        parameters.append(date_bound(date_from))
    if date_to:
        conditions.append(f"created_at < {placeholder}")
        parameters.append(date_bound(date_to + timedelta(days=1)))

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    rows = []
    total_count = 0
    action_options = []
    storage_warning = state.log_storage_warning

    try:
        connection = connect_log_db()
        try:
            with connection:
                count_row = connection.execute(
                    f"SELECT COUNT(*) AS total FROM action_logs{where_clause}",
                    parameters,
                ).fetchone()
                total_count = count_row["total"]

                rows = connection.execute(
                    "SELECT created_at, action, character_name, world_name, comparison_name, "
                    "result, path, status_code, duration_ms, error_type "
                    f"FROM action_logs{where_clause} "
                    "ORDER BY created_at DESC, id DESC LIMIT 500",
                    parameters,
                ).fetchall()
                action_options = [
                    row["action"]
                    for row in connection.execute(
                        "SELECT DISTINCT action FROM action_logs ORDER BY action"
                    ).fetchall()
                ]
        finally:
            connection.close()
    except (sqlite3.Error, psycopg.Error):
        storage_warning = (
            "관리자 로그 저장소에 연결할 수 없습니다. 환경 설정과 데이터베이스 연결을 확인해주세요."
        )
        print("관리자 로그 조회에 실패했습니다.")

    if LOG_DB_BACKEND == "sqlite" and not storage_warning:
        storage_warning = (
            "현재 로그는 SQLite에 저장됩니다. 개발 환경에는 적합하지만 "
            "Render 재배포 후 보존하려면 PostgreSQL 연결이 필요합니다."
        )

    logs = []
    for row in rows:
        item = dict(row)
        item["created_at_display"] = format_admin_log_time(item.get("created_at"))
        logs.append(item)

    return render_template(
        "admin_logs.html",
        logs=logs,
        total_count=total_count,
        displayed_count=min(total_count, 500),
        search_text=search_text,
        selected_action=selected_action,
        selected_result=selected_result,
        date_from_text=date_from_text,
        date_to_text=date_to_text,
        action_options=action_options,
        storage_backend=LOG_DB_BACKEND,
        storage_warning=storage_warning,
        csrf_token=session.setdefault("csrf_token", secrets.token_urlsafe(32))
    )


@admin_bp.route("/logout", methods=["POST"])
@admin_required
def admin_logout():
    submitted_token = request.form.get("csrf_token", "")
    expected_token = session.get("csrf_token", "")
    if not hmac.compare_digest(str(expected_token), str(submitted_token)):
        return "잘못된 요청입니다.", 400
    session.clear()
    return redirect(url_for("admin.admin_login"))
