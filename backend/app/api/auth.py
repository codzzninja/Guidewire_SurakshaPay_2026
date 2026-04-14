from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import json

#auth
from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginIn, RegisterIn, Token, UserOut
from app.services.security import create_access_token, hash_password, verify_password
from app.services.synthetic_earnings import ensure_synthetic_history

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.phone == body.phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")
    if not (body.consent_gps_location and body.consent_upi_account and body.consent_platform_activity):
        raise HTTPException(
            status_code=400,
            detail="Consent required: GPS location, UPI account, and platform activity data",
        )
    now = datetime.now(timezone.utc)
    u = User(
        phone=body.phone,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        platform=body.platform,
        zone_id=body.zone_id,
        upi_id=body.upi_id,
        avg_hours_per_day=body.avg_hours_per_day,
        lat=body.lat,
        lon=body.lon,
        consent_gps_location=body.consent_gps_location,
        consent_upi_account=body.consent_upi_account,
        consent_platform_activity=body.consent_platform_activity,
        consent_captured_at=now,
        active_days_last_365=0,
        kyc_id_type=body.kyc_id_type,
        kyc_document_last4=body.kyc_document_last4,
        kyc_status="verified",
        kyc_verified_at=now,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    ensure_synthetic_history(db, u)
    token = create_access_token(u.id)
    return Token(access_token=token)


@router.post("/login", response_model=Token)
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.phone == body.phone).first()
    if not u or not verify_password(body.password, u.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return Token(access_token=create_access_token(u.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    out = UserOut.model_validate(user)
    try:
        att = json.loads(user.gps_attestation_json or "{}")
    except json.JSONDecodeError:
        att = {}
    samples = att.get("samples")
    n = len(samples) if isinstance(samples, list) else 0
    cap = att.get("captured_at") if isinstance(att.get("captured_at"), str) else None
    return out.model_copy(update={"gps_sample_count": n, "gps_captured_at": cap})
