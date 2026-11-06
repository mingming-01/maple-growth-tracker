"""환경변수와 Flask 기본 설정을 한곳에서 관리한다."""
import os

from dotenv import load_dotenv


def _int_env(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float_env(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


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

    # 외부 API 호출 안정성 설정. 과도한 재시도를 피하도록 횟수와 대기 시간을 제한한다.
    NEXON_API_CONNECT_TIMEOUT = _float_env("NEXON_API_CONNECT_TIMEOUT", 3.05)
    NEXON_API_READ_TIMEOUT = _float_env("NEXON_API_READ_TIMEOUT", 10)
    NEXON_API_RETRIES = _int_env("NEXON_API_RETRIES", 2)
    NEXON_API_RETRY_BACKOFF = _float_env("NEXON_API_RETRY_BACKOFF", 0.35)
    AI_API_TIMEOUT = _float_env("AI_API_TIMEOUT", 30)
    AI_API_RETRIES = _int_env("AI_API_RETRIES", 1)
    AI_API_RETRY_BACKOFF = _float_env("AI_API_RETRY_BACKOFF", 0.5)
