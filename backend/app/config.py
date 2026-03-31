import os

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool = True) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///sentinel.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    _origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
    CORS_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]
    FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
    NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
    MODEL_VERSION = os.environ.get("MODEL_VERSION", "enhanced-v1")

    # Horizonte de predicción (días hasta target_date)
    HORIZON_DAYS = int(os.environ.get("HORIZON_DAYS", "1"))
    # Umbral mínimo de señal; el efectivo es max(base, VOL_THRESHOLD_MULTIPLIER * vol_20d)
    THRESHOLD_BASE_PCT = float(os.environ.get("THRESHOLD_BASE_PCT", "0.003"))
    VOL_THRESHOLD_MULTIPLIER = float(os.environ.get("VOL_THRESHOLD_MULTIPLIER", "0.65"))
    THRESHOLD_MAX_PCT = float(os.environ.get("THRESHOLD_MAX_PCT", "0.045"))
    # Media ARIMA + ETS cuando hay suficiente historia
    PRED_ENSEMBLE = _bool_env("PRED_ENSEMBLE", True)
    MOMENTUM_BLEND = float(os.environ.get("MOMENTUM_BLEND", "0.12"))
    HIGH_VOL_CONFIDENCE_PENALTY = float(os.environ.get("HIGH_VOL_CONFIDENCE_PENALTY", "0.88"))

    # Ingesta: más historia mejora modelos de serie
    COINGECKO_DAYS = int(os.environ.get("COINGECKO_DAYS", "365"))
    YFINANCE_PERIOD = os.environ.get("YFINANCE_PERIOD", "2y")

    # Noticias: ahorrar cuota en APIs gratuitas
    NEWS_MIN_INTERVAL_HOURS = int(os.environ.get("NEWS_MIN_INTERVAL_HOURS", "8"))
    NEWS_PAGE_SIZE = int(os.environ.get("NEWS_PAGE_SIZE", "12"))

    # Correo (cita previa / avisos)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = _bool_env("MAIL_USE_TLS", True)
    MAIL_USE_SSL = _bool_env("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "")
