"""메인 페이지 HTTP 라우트."""
from flask import Blueprint, render_template

page_bp = Blueprint("pages", __name__)


@page_bp.route("/")
def home():
    """메인 캐릭터 검색 화면을 표시한다."""
    return render_template("index.html")
