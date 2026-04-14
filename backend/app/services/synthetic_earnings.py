"""
Automatic synthetic daily earnings — no manual entry.
Uses zone, hours, weekday seasonality, and deterministic noise (demo / cold-start).
Production would replace this with platform-reported earnings.
"""

import json
import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.earning_day import EarningDay
from app.models.user import User

# Typical delivery: Fri/Sat higher, Sun/Mon softer (illustrative)
_WEEKDAY_MULT = [0.88, 0.92, 0.94, 0.98, 1.06, 1.12, 0.84]  # Mon=0 … Sun=6


def _amount_for_day(user: User, d: date) -> tuple[float, int]:
    rng = random.Random(user.id * 1_000_003 + d.toordinal())
    base = 520.0 + (abs(hash(user.zone_id)) % 380)
    scale = 0.72 + (min(user.avg_hours_per_day, 12.0) / 12.0) * 0.48
    mult = _WEEKDAY_MULT[d.weekday()]
    noise = rng.uniform(0.91, 1.09)
    amount = round(base * scale * mult * noise, 0)
    amount = float(max(180.0, min(amount, 2600.0)))
    mins = rng.randint(200, min(720, int(user.avg_hours_per_day * 65)))
    return amount, mins


def ensure_synthetic_history(db: Session, user: User, days: int = 21) -> int:
    """
    If the user has no earning_days rows, create a plausible history.
    Returns number of rows inserted (0 if already had data).
    """
    n = db.query(EarningDay).filter(EarningDay.user_id == user.id).count()
    if n > 0:
        return 0
    today = date.today()
    for i in range(days, 0, -1):
        d = today - timedelta(days=i)
        amt, mins = _amount_for_day(user, d)
        db.add(
            EarningDay(
                user_id=user.id,
                earn_date=d,
                amount=amt,
                minutes_online=mins,
            )
        )
    db.commit()
    last7 = (
        db.query(EarningDay)
        .filter(EarningDay.user_id == user.id)
        .order_by(EarningDay.earn_date.desc())
        .limit(7)
        .all()
    )
    asc7 = sorted(last7, key=lambda r: r.earn_date)
    user.earnings_json = json.dumps([r.amount for r in asc7])
    db.add(user)
    db.commit()
    return days


def resimulate_synthetic_history(db: Session, user: User, days: int = 21) -> int:
    """Replace all synthetic rows (for demo reset)."""
    db.query(EarningDay).filter(EarningDay.user_id == user.id).delete()
    db.commit()
    return ensure_synthetic_history(db, user, days=days)
