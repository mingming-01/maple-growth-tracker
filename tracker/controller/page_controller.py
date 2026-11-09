"""React 단일 진입점과 메인 페이지 제공 라우트."""
from pathlib import Path

from flask import Blueprint, abort, current_app, send_from_directory

page_bp = Blueprint("pages", __name__)


def _react_build_dir():
    return Path(current_app.static_folder) / "react-preview"


@page_bp.route("/")
def home():
    """빌드된 React 앱만 메인 화면으로 제공한다. 레거시 화면 폴백은 없다."""
    dist_dir = _react_build_dir()
    if not (dist_dir / "index.html").is_file():
        abort(
            503,
            description=(
                "React 프런트엔드 빌드가 없습니다. "
                "배포 빌드에서 npm --prefix frontend run build를 실행해야 합니다."
            ),
        )
    return send_from_directory(dist_dir, "index.html")
