"""Playwright E2E용 Flask 개발 서버 진입점."""

from pathlib import Path
import sys


# 스크립트 경로(scripts/)가 아닌 저장소 루트를 기준으로 앱 패키지를 찾는다.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tracker import create_app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, use_reloader=False)
