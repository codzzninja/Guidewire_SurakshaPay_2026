from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load .env from the backend folder (next to app/), not from whatever cwd uvicorn uses.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"
# Exposed for /health/integrations (path only, no secrets)
BACKEND_ENV_FILE = _ENV_FILE


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        # utf-8-sig strips BOM — otherwise first key can become "\ufeffOPENWEATHER_..."
        env_file_encoding="utf-8-sig",
        # Empty OPENWEATHER_API_KEY in Windows/User env must not override values from .env
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "SurakshaPay API"
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    database_url: str = "sqlite:///./surakshapay.db"
    redis_url: str = "redis://localhost:6379/0"

    # TTL for cached weather/AQI/RSS bundle (pricing + /monitoring/live). Celery refreshes on same cadence.
    environment_cache_ttl_seconds: int = 300

    # --- Real integrations (Phase 2) ---
    # Set ALLOW_MOCKS=true only for local dev without API keys.
    allow_mocks: bool = False
    # Hackathon/demo: allow POST /monitoring/evaluate demo_weather_integrity_mismatch without full ALLOW_MOCKS.
    demo_weather_edge_case: bool = False
    # Compliance gates can be toggled for demos without changing code paths.
    enforce_lockout: bool = False
    enforce_min_active_days: bool = False
    min_active_days_for_payout: int = 90

    openweather_api_key: str = ""
    waqi_api_token: str = ""

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    # Webhook signing secret from Razorpay Dashboard → Webhooks (not the API key secret)
    razorpay_webhook_secret: str = ""
    # If true (default), payouts are simulated when keys are missing — other APIs stay real.
    # Set RAZORPAY_OPTIONAL=false to require keys (strict).
    razorpay_optional: bool = True
    # Claim payout processor mode. `upi_simulator` is demo-safe and does not move real money.
    payout_provider: str = "upi_simulator"

    # Stripe Test Mode (sk_test_...) — alternative when Razorpay is unavailable. Dashboard: https://dashboard.stripe.com/test/apikeys
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Where Checkout redirects after pay (must match CORS / browser origin). e.g. http://localhost:5173
    frontend_base_url: str = "http://localhost:5173"

    # Public RSS (real HTTP). Default: ReliefWeb India updates.
    government_rss_url: str = "https://reliefweb.int/updates/rss.xml?search=country:India"

    default_city_lat: float = 13.0827
    default_city_lon: float = 80.2707
    demo_zone_id: str = "chennai-t-nagar"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Phase 3 insurer dashboard — send header `X-Suraksha-Admin-Token: <value>`
    admin_analytics_token: str = ""
    # How many distinct work zones to sample for multi-market weather (by worker count).
    insurer_weather_max_markets: int = 8

    @field_validator(
        "openweather_api_key",
        "waqi_api_token",
        "razorpay_key_id",
        "razorpay_key_secret",
        "razorpay_webhook_secret",
        "stripe_secret_key",
        "stripe_webhook_secret",
        mode="after",
    )
    @classmethod
    def strip_secret_whitespace(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v


settings = Settings()
