"""관리자 인증과 운영 로그 HTTP 라우트."""
from datetime import date, datetime, timedelta
import hmac
import time
import secrets
import sqlite3

import psycopg
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from tracker.runtime import KOREA_TIMEZONE, connect_log_db, get_runtime_state
from tracker.services.admin_log_service import admin_required, format_admin_log_time
from tracker.services.performance_metrics import (
    increment_metric,
    observe_metric,
    performance_metrics_snapshot,
)
from tracker.services.request_limits import (
    admin_login_lockout_remaining,
    clear_admin_login_failures,
    record_admin_login_failure,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _measure_admin_log_query(query_name, operation, backend):
    """관리자 로그 쿼리별 실행 및 결과 fetch 시간을 기록한다."""
    started_at = time.perf_counter()
    try:
        return operation()
    finally:
        labels = {"backend": backend, "store": "admin_logs", "query": query_name}
        increment_metric("db.query_executions", **labels)
        observe_metric("db.query_ms", (time.perf_counter() - started_at) * 1000, **labels)


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    """해시 비밀번호와 CSRF를 검증하고 반복 실패는 IP 단위로 잠근다."""
    admin_username = current_app.config.get("ADMIN_USERNAME", "")
    admin_password_hash = current_app.config.get("ADMIN_PASSWORD_HASH", "")
    is_production = bool(current_app.config.get("IS_PRODUCTION", False))
    admin_password = "" if is_production else current_app.config.get("ADMIN_PASSWORD", "")
    configured = bool(admin_username and (
        admin_password_hash or (admin_password and not is_production)
    ))
    if session.get("admin_authenticated"):
        return redirect(url_for("admin.admin_logs"))

    csrf_token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    error = None
    remaining = admin_login_lockout_remaining(request.remote_addr)
    if request.method == "POST":
        if remaining:
            error = f"로그인 시도가 제한되어 있습니다. {remaining}초 후 다시 시도해주세요."
        else:
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

            if not configured:
                error = "관리자 인증 환경변수가 설정되지 않았습니다. 운영 환경은 ADMIN_PASSWORD_HASH가 필요합니다."
            elif not valid_token:
                error = "잘못된 요청입니다. 페이지를 새로고침한 뒤 다시 시도해주세요."
            elif hmac.compare_digest(admin_username, username) and password_valid:
                clear_admin_login_failures(request.remote_addr)
                session.clear()
                session["admin_authenticated"] = True
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(url_for("admin.admin_logs"))
            else:
                remaining = record_admin_login_failure(request.remote_addr)
                error = (
                    f"로그인 실패 횟수를 초과했습니다. {remaining}초 후 다시 시도해주세요."
                    if remaining else "아이디 또는 비밀번호를 확인해주세요."
                )

    return render_template(
        "admin_login.html",
        csrf_token=csrf_token,
        error=error,
        configured=configured,
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
        return value if log_db_backend == "postgres" else value.isoformat(timespec="seconds")

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

    query_started = time.perf_counter()
    query_count = 0
    try:
        connection = connect_log_db()
        try:
            with connection:
                count_row = _measure_admin_log_query(
                    "count",
                    lambda: connection.execute(
                        f"SELECT COUNT(*) AS total FROM action_logs{where_clause}",
                        parameters,
                    ).fetchone(),
                    log_db_backend,
                )
                query_count += 1
                total_count = count_row["total"]

                rows = _measure_admin_log_query(
                    "page",
                    lambda: connection.execute(
                        "SELECT created_at, action, character_name, world_name, comparison_name, "
                        "result, path, status_code, duration_ms, error_type "
                        f"FROM action_logs{where_clause} "
                        "ORDER BY created_at DESC, id DESC LIMIT 500",
                        parameters,
                    ).fetchall(),
                    log_db_backend,
                )
                query_count += 1
                action_rows = _measure_admin_log_query(
                    "actions",
                    lambda: connection.execute(
                        "SELECT DISTINCT action FROM action_logs ORDER BY action"
                    ).fetchall(),
                    log_db_backend,
                )
                action_options = [row["action"] for row in action_rows]
                query_count += 1
        finally:
            connection.close()
    except (sqlite3.Error, psycopg.Error):
        storage_warning = (
            "관리자 로그 저장소에 연결할 수 없습니다. 환경 설정과 데이터베이스 연결을 확인해주세요."
        )
        print("관리자 로그 조회에 실패했습니다.")
    finally:
        increment_metric("db.operations", operation="admin_logs.select")
        increment_metric("db.sql_statements", query_count, operation="admin_logs.select")
        observe_metric(
            "db.operation_ms",
            (time.perf_counter() - query_started) * 1000,
            operation="admin_logs.select",
        )

    if log_db_backend == "sqlite" and not storage_warning:
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
        storage_backend=log_db_backend,
        storage_warning=storage_warning,
        snapshot_storage_backend=state.snapshot_db_backend,
        snapshot_storage_warning=state.snapshot_storage_warning,
        csrf_token=session.setdefault("csrf_token", secrets.token_urlsafe(32))
    )


@admin_bp.route("/api/logs")
@admin_required
def admin_logs_api():
    """React 관리자 화면용 JSON 로그 API. 기존 세션 인증과 필터 조건을 그대로 사용한다."""
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
        return value if log_db_backend == "postgres" else value.isoformat(timespec="seconds")

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

    query_started = time.perf_counter()
    query_count = 0
    try:
        connection = connect_log_db()
        try:
            with connection:
                count_row = connection.execute(
                    f"SELECT COUNT(*) AS total FROM action_logs{where_clause}",
                    parameters,
                ).fetchone()
                query_count += 1
                total_count = count_row["total"]

                rows = connection.execute(
                    "SELECT created_at, action, character_name, world_name, comparison_name, "
                    "result, path, status_code, duration_ms, error_type "
                    f"FROM action_logs{where_clause} "
                    "ORDER BY created_at DESC, id DESC LIMIT 500",
                    parameters,
                ).fetchall()
                query_count += 1
                action_options = [
                    row["action"]
                    for row in connection.execute(
                        "SELECT DISTINCT action FROM action_logs ORDER BY action"
                    ).fetchall()
                ]
                query_count += 1
        finally:
            connection.close()
    except (sqlite3.Error, psycopg.Error):
        storage_warning = (
            "관리자 로그 저장소에 연결할 수 없습니다. 환경 설정과 데이터베이스 연결을 확인해주세요."
        )
        print("관리자 로그 조회에 실패했습니다.")
    finally:
        increment_metric("db.operations", operation="admin_logs.select")
        increment_metric("db.sql_statements", query_count, operation="admin_logs.select")
        observe_metric(
            "db.operation_ms",
            (time.perf_counter() - query_started) * 1000,
            operation="admin_logs.select",
        )

    if log_db_backend == "sqlite" and not storage_warning:
        storage_warning = (
            "현재 로그는 SQLite에 저장됩니다. Render 재배포 후 보존하려면 PostgreSQL 연결이 필요합니다."
        )

    logs = []
    for row in rows:
        item = dict(row)
        item["created_at_display"] = format_admin_log_time(item.get("created_at"))
        logs.append(item)

    return jsonify({
        "logs": logs,
        "totalCount": total_count,
        "displayedCount": min(total_count, 500),
        "actionOptions": action_options,
        "storageBackend": log_db_backend,
        "storageWarning": storage_warning,
        "snapshotStorageBackend": state.snapshot_db_backend,
        "snapshotStorageWarning": state.snapshot_storage_warning,
        "csrfToken": session.setdefault("csrf_token", secrets.token_urlsafe(32)),
    })


@admin_bp.route("/api/performance")
@admin_required
def admin_performance_api():
    """현재 Gunicorn worker 프로세스의 성능 계측 요약을 반환한다."""
    return jsonify(performance_metrics_snapshot())


@admin_bp.route("/logout", methods=["POST"])
@admin_required
def admin_logout():
    submitted_token = request.form.get("csrf_token", "")
    expected_token = session.get("csrf_token", "")
    if not hmac.compare_digest(str(expected_token), str(submitted_token)):
        return "잘못된 요청입니다.", 400
    session.clear()
    return redirect(url_for("admin.admin_login"))
