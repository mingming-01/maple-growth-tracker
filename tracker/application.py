"""Flask 애플리케이션 팩토리."""
import os
import warnings
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
    is_production = bool(app.config.get("IS_PRODUCTION", False))
    configured_secret = app.config.get("FLASK_SECRET_KEY")
    if is_production and not configured_secret:
        warnings.warn(
            "운영 환경에 FLASK_SECRET_KEY가 설정되지 않았습니다. "
            "재시작 시 세션이 무효화될 수 있으므로 고정된 비밀키를 설정하세요.",
            RuntimeWarning,
        )
    elif is_production and len(str(configured_secret)) < 32:
        warnings.warn("운영 환경의 FLASK_SECRET_KEY는 32자 이상을 권장합니다.", RuntimeWarning)
    if is_production and not app.config.get("ADMIN_PASSWORD_HASH"):
        warnings.warn(
            "운영 환경에 ADMIN_PASSWORD_HASH가 설정되지 않아 관리자 로그인이 비활성화됩니다.",
            RuntimeWarning,
        )
    app.secret_key = configured_secret or os.urandom(32)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(app.config.get("FLASK_COOKIE_SECURE", False) or is_production),
        MAX_CONTENT_LENGTH=64 * 1024,
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
