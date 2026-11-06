"""메인 페이지 HTTP 라우트와 React 및 레거시 화면 제공."""
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    send_from_directory,
    url_for,
)

page_bp = Blueprint("pages", __name__)


def _react_build_dir():
    return Path(current_app.static_folder) / "react-preview"


@page_bp.route("/")
def home():
    """React 빌드가 있으면 메인 화면으로 제공하고, 없으면 기존 화면으로 폴백한다."""
    dist_dir = _react_build_dir()
    if (dist_dir / "index.html").is_file():
        return send_from_directory(dist_dir, "index.html")
    return render_template("index.html")


@page_bp.route("/legacy")
def legacy_home_redirect():
    """기존 화면의 정규 경로로 이동한다."""
    return redirect(url_for("pages.legacy_home"))


@page_bp.route("/legacy/")
def legacy_home():
    """React 전환 후에도 기존 화면을 비교·복구할 수 있도록 보존한다."""
    return render_template("index.html")


@page_bp.route("/preview")
def react_preview_redirect():
    """React 미리보기의 정규 경로로 이동한다."""
    return redirect(url_for("pages.react_preview"))


@page_bp.route("/preview/")
def react_preview():
    """빌드된 React 화면을 별도 미리보기 경로로 제공한다."""
    dist_dir = _react_build_dir()
    if not (dist_dir / "index.html").is_file():
        return render_template("react_preview_unavailable.html"), 503
    return send_from_directory(dist_dir, "index.html")


@page_bp.route("/preview/<path:asset_path>")
def react_preview_asset(asset_path):
    """기존 상대 경로 빌드와의 호환성을 위해 미리보기 산출물을 제공한다."""
    dist_dir = _react_build_dir()
    if not dist_dir.is_dir():
        abort(404)
    return send_from_directory(dist_dir, asset_path)
