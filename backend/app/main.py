from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import analytics, auth, claims, monitoring, payments, policies, users
from app.config import BACKEND_ENV_FILE, settings
from app.database import init_db
from app.services.errors import IntegrationError


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SurakshaPay API", lifespan=lifespan)


@app.exception_handler(IntegrationError)
async def integration_handler(_request: Request, exc: IntegrationError):
    return JSONResponse(
        status_code=503,
        content={"detail": exc.message},
        headers={"X-Suraksha-Integration": exc.source},
    )

_cors = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
# Capacitor Android/iOS origins for local mobile shells.
for _o in ("http://localhost", "capacitor://localhost"):
    if _o not in _cors:
        _cors.append(_o)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(policies.router)
app.include_router(claims.router)
app.include_router(monitoring.router)
app.include_router(users.router)
app.include_router(payments.router)
app.include_router(analytics.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "surakshapay"}


@app.get("/health/integrations")
def integration_status():
    """Which real integrations are configured (no secrets exposed)."""
    from pathlib import Path

    model_path = Path(__file__).resolve().parent / "ml" / "premium_xgb.pkl"
    rp_ok = bool(settings.razorpay_key_id and settings.razorpay_key_secret)
    st_ok = bool(settings.stripe_secret_key.strip())
    return {
        "dotenv_path": str(BACKEND_ENV_FILE),
        "dotenv_exists": BACKEND_ENV_FILE.is_file(),
        "allow_mocks": settings.allow_mocks,
        "openweather_configured": bool(settings.openweather_api_key),
        "waqi_configured": bool(settings.waqi_api_token),
        "razorpay_configured": rp_ok,
        "razorpay_webhook_configured": bool(settings.razorpay_webhook_secret.strip()),
        "razorpay_optional": settings.razorpay_optional,
        "razorpay_using_simulation": settings.razorpay_optional and not rp_ok,
        "stripe_configured": st_ok,
        "stripe_webhook_configured": bool(settings.stripe_webhook_secret.strip()),
        "frontend_base_url": settings.frontend_base_url,
        "payout_provider": settings.payout_provider,
        "compliance_controls": {
            "dpdp_consent_required": True,
            "kyc_required_for_premium_and_payout": True,
            "adverse_selection_lockout_enabled": settings.enforce_lockout,
            "min_active_days_enforced": settings.enforce_min_active_days,
            "min_active_days_for_payout": settings.min_active_days_for_payout,
        },
        "rss_url_configured": bool(settings.government_rss_url.strip()),
        "premium_model_file": model_path.exists(),
        "environment_cache_ttl_seconds": settings.environment_cache_ttl_seconds,
        "fraud_engine": "isolation_forest_plus_msts_phase3",
        "gps_zone_radius_km_default": 32,
        "gps_zone_granular": True,
    }
