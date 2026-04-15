from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.claim import TriggerSimulateIn
from app.services.environment_cache import get_or_refresh_env_rss
from app.services.triggers import live_payload_from_env_rss, run_pipeline_for_user

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/live")
async def live_triggers(
    refresh: bool = Query(False, description="Bypass cache and fetch OpenWeather/WAQI/RSS now"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Live disruption flags + details. Uses DB cache (TTL) unless `refresh=true`.
    Includes `data_freshness` (fetched_at, age_seconds, cache_hit).
    """
    env, rss, meta = await get_or_refresh_env_rss(db, user, force_refresh=refresh)
    payload = live_payload_from_env_rss(env, rss)
    return {**payload, "data_freshness": meta}


@router.post("/evaluate")
async def evaluate_self(
    body: TriggerSimulateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run payout pipeline. Use force_mock_disruption=true for a guaranteed demo path."""
    return await run_pipeline_for_user(
        db,
        user,
        force_mock_disruption=body.force_mock_disruption,
        demo_weather_integrity_mismatch=body.demo_weather_integrity_mismatch,
    )
