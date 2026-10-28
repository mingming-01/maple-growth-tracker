"""Flask HTTP 컨트롤러."""

from app import *


@app.route("/")
def home():
    """메인 캐릭터 검색 화면을 표시한다."""
    return render_template("index.html")
