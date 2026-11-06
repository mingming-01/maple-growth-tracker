"""Playwright E2E용 Flask 개발 서버 진입점."""

from tracker import create_app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, use_reloader=False)
