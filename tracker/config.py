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
    NEXON_API_MIN_INTERVAL = _float_env("NEXON_API_MIN_INTERVAL", 0.22)
    EXTERNAL_API_MAX_RETRY_AFTER_WAIT_SECONDS = _float_env("EXTERNAL_API_MAX_RETRY_AFTER_WAIT_SECONDS", 5.0)
    # 캐시 미스와 강제 새로고침을 구분해 공개 데이터 API를 보호한다.
    API_REQUEST_LIMITS_ENABLED = os.getenv("API_REQUEST_LIMITS_ENABLED", "true").lower() == "true"
    API_REQUEST_LIMIT_WINDOW_SECONDS = _int_env("API_REQUEST_LIMIT_WINDOW_SECONDS", 60)
    API_REQUESTS_PER_MINUTE_PER_IP = _int_env("API_REQUESTS_PER_MINUTE_PER_IP", 60)
    API_REFRESHES_PER_MINUTE_PER_IP = _int_env("API_REFRESHES_PER_MINUTE_PER_IP", 12)
    API_RATE_LIMIT_MAX_CLIENTS = _int_env("API_RATE_LIMIT_MAX_CLIENTS", 10000)
    TRUSTED_PROXY_HOPS = max(0, _int_env("TRUSTED_PROXY_HOPS", 0))
    AI_MAX_REQUESTS_PER_MINUTE = _int_env("AI_MAX_REQUESTS_PER_MINUTE", 5)
    AI_MAX_REQUESTS_PER_DAY_PER_IP = _int_env("AI_MAX_REQUESTS_PER_DAY_PER_IP", 20)
    AI_MAX_REQUESTS_PER_DAY_GLOBAL = _int_env("AI_MAX_REQUESTS_PER_DAY_GLOBAL", 100)
    ADMIN_LOGIN_MAX_ATTEMPTS = _int_env("ADMIN_LOGIN_MAX_ATTEMPTS", 5)
    ADMIN_LOGIN_WINDOW_SECONDS = _int_env("ADMIN_LOGIN_WINDOW_SECONDS", 900)
    ADMIN_LOGIN_LOCKOUT_SECONDS = _int_env("ADMIN_LOGIN_LOCKOUT_SECONDS", 900)
    IS_PRODUCTION = (
        os.getenv("RENDER", "").lower() == "true"
        or os.getenv("FLASK_ENV", "").lower() == "production"
    )
