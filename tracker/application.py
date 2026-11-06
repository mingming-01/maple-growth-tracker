"""Flask 애플리케이션 팩토리."""
import os
from pathlib import Path

from flask import Flask

from tracker.config import Config
from tracker import runtime


def create_app(test_config=None):
    """환경별 설정을 적용한 Flask 앱을 생성하고 기능별 Blueprint를 등록한다."""
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        "tracker",
        root_path=str(project_root),
        template_folder="templates",
        static_folder="static",
        instance_relative_config=True,
    )
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    app.json.ensure_ascii = False
    app.secret_key = app.config.get("FLASK_SECRET_KEY") or os.urandom(32)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(app.config.get("FLASK_COOKIE_SECURE", False)),
    )

    runtime.configure_runtime(app)

    from tracker.controller.page_controller import page_bp
    from tracker.controller.admin_controller import admin_bp
    from tracker.controller.character_controller import character_bp
    from tracker.controller.history_controller import history_bp
    from tracker.controller.ai_controller import ai_bp
    from tracker.services.ai_analysis_service import (
        generate_ai_analysis,
        generate_ai_comparison,
    )

    # app 모듈을 직접 import하던 기존 테스트·운영 스크립트의 호출 호환성을 유지한다.
    runtime.generate_ai_analysis = generate_ai_analysis
    runtime.generate_ai_comparison = generate_ai_comparison

    app.register_blueprint(page_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(character_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(ai_bp)

    app.before_request(runtime.start_request_timer)
    app.after_request(runtime.record_user_action)
    app.register_error_handler(Exception, runtime.handle_unexpected_error)
    return app
