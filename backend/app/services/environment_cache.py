"""DB-backed cache for weather + AQI + RSS (real-time freshness metadata)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.environment_snapshot import EnvironmentSnapshot
from app.models.user import User
from app.services.errors import IntegrationError
from app.services.rss_alerts import fetch_social_rss_signals
from app.services.weather import fetch_all_triggers

_HISTORY_MAX = 48


def merge_env_payload(
    prev_json: str | None,
    env: dict[str, Any],
    rss: dict[str, Any],
    *,
    max_hist: int = _HISTORY_MAX,
) -> str:
    """Append compact weather rows for fraud / insurer analytics (Phase 3)."""
    prev: dict[str, Any] = {}
    if prev_json:
        try:
            prev = json.loads(prev_json)
        except json.JSONDecodeError:
            prev = {}
    hist = prev.get("history") if isinstance(prev.get("history"), list) else []
    w = env.get("weather") or {}
    a = env.get("aqi") or {}
    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "rain_tr": bool(w.get("rain_trigger")),
        "heat_tr": bool(w.get("heat_trigger")),
        "aqi_sev": bool(a.get("severe_pollution")),
        "rain_mm_h": float(w.get("rain_mm_hour") or 0),
        "rain_24": float(w.get("forecast_rain_24h_mm") or 0),
        "temp_c": float(w.get("temp_c") or 0),
        "max_t_24": float(w.get("max_temp_next_24h") or 0),
        "curfew": bool(rss.get("curfew_social")),
        "zone_close": bool(rss.get("traffic_zone_closure")),
    }
    new_hist = (hist + [entry])[-max_hist:]
    return json.dumps({"env": env, "rss": rss, "history": new_hist})


def load_weather_history(db: Session, user_id: int, limit: int = 24) -> list[dict[str, Any]]:
    row = db.query(EnvironmentSnapshot).filter(EnvironmentSnapshot.user_id == user_id).first()
    if not row:
        return []
    try:
        data = json.loads(row.payload_json)
    except json.JSONDecodeError:
        return []
    hist = data.get("history")
    if not isinstance(hist, list):
        return []
    return hist[-limit:]


async def fetch_env_rss_live(user: User) -> tuple[dict[str, Any], dict[str, Any]]:
    env = await fetch_all_triggers(user.lat, user.lon)
    try:
        rss = await fetch_social_rss_signals()
    except IntegrationError:
        rss = {
            "curfew_social": False,
            "traffic_zone_closure": False,
            "source": "skipped",
        }
    return env, rss


def _freshness_meta(
    *,
    cache_hit: bool,
    fetched_at: datetime,
    ttl_seconds: int,
    stale_fallback: bool = False,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    age = max(0.0, (now - fetched_at).total_seconds())
    return {
        "cache_hit": cache_hit,
        "stale_fallback": stale_fallback,
        "fetched_at": fetched_at.isoformat(),
        "age_seconds": round(age, 1),
        "ttl_seconds": ttl_seconds,
        "next_refresh_in_seconds": max(0, int(ttl_seconds - age)),
    }


async def get_or_refresh_env_rss(
    db: Session,
    user: User,
    *,
    force_refresh: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """
    Returns (env, rss, freshness_meta). Uses DB when row is younger than TTL.
    On live fetch failure, returns last cached row if any (stale_fallback).
    """
    ttl = settings.environment_cache_ttl_seconds
    row = db.query(EnvironmentSnapshot).filter(EnvironmentSnapshot.user_id == user.id).first()
    now = datetime.now(timezone.utc)

    if row and not force_refresh:
        ft = row.fetched_at
        if ft.tzinfo is None:
            ft = ft.replace(tzinfo=timezone.utc)
        age = (now - ft).total_seconds()
        if age < ttl:
            data = json.loads(row.payload_json)
            return (
                data["env"],
                data["rss"],
                {
                    **_freshness_meta(cache_hit=True, fetched_at=ft, ttl_seconds=ttl),
                    "history_points": len(data["history"]) if isinstance(data.get("history"), list) else 0,
                },
            )

    try:
        env, rss = await fetch_env_rss_live(user)
    except IntegrationError:
        if row:
            data = json.loads(row.payload_json)
            ft = row.fetched_at
            if ft.tzinfo is None:
                ft = ft.replace(tzinfo=timezone.utc)
            return (
                data["env"],
                data["rss"],
                _freshness_meta(
                    cache_hit=True,
                    fetched_at=ft,
                    ttl_seconds=ttl,
                    stale_fallback=True,
                ),
            )
        raise

    prev = row.payload_json if row else None
    payload = merge_env_payload(prev, env, rss)
    if row:
        row.payload_json = payload
        row.fetched_at = now
    else:
        db.add(EnvironmentSnapshot(user_id=user.id, payload_json=payload, fetched_at=now))
    db.commit()

    return env, rss, _freshness_meta(cache_hit=False, fetched_at=now, ttl_seconds=ttl)


def upsert_environment_snapshot(db: Session, user: User, env: dict[str, Any], rss: dict[str, Any]) -> None:
    """Upsert snapshot (Celery batch refresh)."""
    now = datetime.now(timezone.utc)
    row = db.query(EnvironmentSnapshot).filter(EnvironmentSnapshot.user_id == user.id).first()
    prev = row.payload_json if row else None
    payload = merge_env_payload(prev, env, rss)
    if row:
        row.payload_json = payload
        row.fetched_at = now
    else:
        db.add(EnvironmentSnapshot(user_id=user.id, payload_json=payload, fetched_at=now))
    db.commit()
