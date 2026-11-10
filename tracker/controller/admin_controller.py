"""관리자 인증과 운영 로그 HTTP 라우트."""
from datetime import date
import hmac
import secrets
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from tracker.runtime import get_runtime_state
from tracker.services.admin_log_service import admin_required, format_admin_log_time
from tracker.services.performance_metrics import performance_metrics_snapshot
from tracker.services.request_limits import (
    admin_login_lockout_remaining,
    clear_admin_login_failures,
    record_admin_login_failure,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


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

def _load_admin_log_view_data():
    """요청 필터를 정규화하고 서비스에서 조회한 로그를 화면 데이터로 변환한다."""
    state = get_runtime_state()
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

    if selected_result not in ("성공", "실패"):
        selected_result = ""

    result = state.admin_log_service.list_logs(
        search_text=search_text,
        selected_action=selected_action,
        selected_result=selected_result,
        date_from=date_from,
        date_to=date_to,
    )
    logs = []
    for row in result["rows"]:
        item = dict(row)
        item["created_at_display"] = format_admin_log_time(item.get("created_at"))
        logs.append(item)

    return {
        "state": state,
        "logs": logs,
        "total_count": result["total_count"],
        "action_options": result["action_options"],
        "storage_backend": result["storage_backend"],
        "storage_warning": result["storage_warning"],
        "search_text": search_text,
        "selected_action": selected_action,
        "selected_result": selected_result,
        "date_from_text": date_from_text,
        "date_to_text": date_to_text,
    }


@admin_bp.route("/logs")
@admin_required
def admin_logs():
    """검색 조건을 적용해 관리자 운영 로그를 시간 역순으로 표시한다."""
    data = _load_admin_log_view_data()
    state = data["state"]
    return render_template(
        "admin_logs.html",
        logs=data["logs"],
        total_count=data["total_count"],
        displayed_count=min(data["total_count"], 500),
        search_text=data["search_text"],
        selected_action=data["selected_action"],
        selected_result=data["selected_result"],
        date_from_text=data["date_from_text"],
        date_to_text=data["date_to_text"],
        action_options=data["action_options"],
        storage_backend=data["storage_backend"],
        storage_warning=data["storage_warning"],
        snapshot_storage_backend=state.snapshot_db_backend,
        snapshot_storage_warning=state.snapshot_storage_warning,
        csrf_token=session.setdefault("csrf_token", secrets.token_urlsafe(32)),
    )


@admin_bp.route("/api/logs")
@admin_required
def admin_logs_api():
    """React 관리자 화면용 JSON 로그 API. 기존 세션 인증과 필터 조건을 그대로 사용한다."""
    data = _load_admin_log_view_data()
    state = data["state"]
    return jsonify({
        "logs": data["logs"],
        "totalCount": data["total_count"],
        "displayedCount": min(data["total_count"], 500),
        "actionOptions": data["action_options"],
        "storageBackend": data["storage_backend"],
        "storageWarning": data["storage_warning"],
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
