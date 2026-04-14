import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.earning_day import EarningDay
from app.models.user import User
from app.services.synthetic_earnings import ensure_synthetic_history, resimulate_synthetic_history

router = APIRouter(prefix="/users", tags=["users"])

MAX_GPS_SAMPLES = 48


class GpsSampleIn(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    accuracy: float | None = Field(None, ge=0, le=5000)
    speed: float | None = None
    heading: float | None = None
    ts: int | None = None


class GpsAttestationIn(BaseModel):
    """Device geolocation trace for MSTS / anti-spoofing (README §18)."""

    samples: list[GpsSampleIn] = Field(default_factory=list, max_length=MAX_GPS_SAMPLES)
    source: str = "device_geolocation"
    captured_at: str | None = None


class ProfilePatch(BaseModel):
    zone_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    gps_attestation: GpsAttestationIn | None = None


@router.patch("/me/profile")
def patch_profile(
    body: ProfilePatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.zone_id is not None:
        user.zone_id = body.zone_id
    if body.lat is not None:
        if not -90 <= body.lat <= 90:
            raise HTTPException(400, "Invalid latitude")
        user.lat = body.lat
    if body.lon is not None:
        if not -180 <= body.lon <= 180:
            raise HTTPException(400, "Invalid longitude")
        user.lon = body.lon

    if body.gps_attestation is not None:
        raw = body.gps_attestation.model_dump()
        if not raw.get("captured_at"):
            raw["captured_at"] = datetime.now(timezone.utc).isoformat()
        samples = raw.get("samples") or []
        if len(samples) > MAX_GPS_SAMPLES:
            raise HTTPException(400, "Too many GPS samples")
        if len(samples) >= 1:
            # Pin profile coordinates to trace centroid for weather / zone checks
            mlat = sum(float(s["lat"]) for s in samples) / len(samples)
            mlon = sum(float(s["lon"]) for s in samples) / len(samples)
            user.lat = round(mlat, 7)
            user.lon = round(mlon, 7)

        user.gps_attestation_json = json.dumps(raw)

    db.add(user)
    db.commit()
    db.refresh(user)
    n_stored = 0
    if body.gps_attestation is not None:
        n_stored = len(body.gps_attestation.samples)
    return {
        "ok": True,
        "zone_id": user.zone_id,
        "lat": user.lat,
        "lon": user.lon,
        "gps_samples_stored": n_stored,
    }


@router.get("/me/daily-earnings")
def list_daily_earnings(
    limit: int = 40,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_synthetic_history(db, user)
    limit = min(max(limit, 1), 90)
    rows = (
        db.query(EarningDay)
        .filter(EarningDay.user_id == user.id)
        .order_by(EarningDay.earn_date.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "earn_date": r.earn_date.isoformat(),
            "amount": r.amount,
            "minutes_online": r.minutes_online,
        }
        for r in rows
    ]


@router.post("/me/earnings/resimulate")
def resimulate_earnings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Demo only: regenerate synthetic history from zone + hours."""
    n = resimulate_synthetic_history(db, user)
    return {"ok": True, "days_generated": n, "source": "synthetic_model"}
