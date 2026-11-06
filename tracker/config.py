"""환경변수와 Flask 기본 설정을 한곳에서 관리한다."""
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
    FLASK_COOKIE_SECURE = os.getenv("FLASK_COOKIE_SECURE", "").lower() == "true"

    NEXON_API_KEY = os.getenv("NEXON_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
    ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

    GROWTH_DATABASE_URL = os.getenv("GROWTH_DATABASE_URL", "").strip()
