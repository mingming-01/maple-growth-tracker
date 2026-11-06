"""메인 페이지 HTTP 라우트와 React 미리보기 정적 파일 제공."""
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


@page_bp.route("/")
def home():
    """기존 메인 캐릭터 검색 화면을 표시한다."""
    return render_template("index.html")


@page_bp.route("/preview")
def react_preview_redirect():
    """React 미리보기의 정규 경로로 이동한다."""
    return redirect(url_for("pages.react_preview"))


@page_bp.route("/preview/")
def react_preview():
    """빌드된 React 미리보기를 제공하며 기존 메인 화면은 변경하지 않는다."""
    dist_dir = Path(current_app.static_folder) / "react-preview"
    if not (dist_dir / "index.html").is_file():
        return render_template("react_preview_unavailable.html"), 503

    return send_from_directory(dist_dir, "index.html")


@page_bp.route("/preview/<path:asset_path>")
def react_preview_asset(asset_path):
    """React 빌드 산출물만 미리보기 경로 아래에서 제공한다."""
    dist_dir = Path(current_app.static_folder) / "react-preview"
    if not dist_dir.is_dir():
        abort(404)

    return send_from_directory(dist_dir, asset_path)