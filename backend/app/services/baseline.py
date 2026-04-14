"""Weighted 7-day WMA + optional day-of-week blend using logged daily earnings."""

import json
from datetime import date, timedelta
from statistics import median
from typing import Any

from sqlalchemy.orm import Session

from app.models.earning_day import EarningDay
from app.models.user import User

WEIGHTS = [0.10, 0.10, 0.12, 0.13, 0.15, 0.18, 0.22]


def weighted_baseline(earnings_json: str) -> float:
    try:
        arr = [float(x) for x in json.loads(earnings_json)]
    except (json.JSONDecodeError, TypeError, ValueError):
        arr = [800.0] * 7
    if len(arr) < 7:
        arr = (arr + [800.0] * 7)[:7]
    return sum(w * e for w, e in zip(WEIGHTS, arr[-7:]))


def effective_daily_baseline(db: Session, user: User) -> tuple[float, dict[str, Any]]:
    """
    Prefer logged daily rows: blend last-7 WMA (same weights as README) with
    median earnings on the same weekday (last ~8 weeks). Falls back to earnings_json.
    """
    meta: dict[str, Any] = {"method": "wma_json", "days_logged": 0}

    cutoff = date.today() - timedelta(days=56)
    rows = (
        db.query(EarningDay)
        .filter(EarningDay.user_id == user.id, EarningDay.earn_date >= cutoff)
        .order_by(EarningDay.earn_date.desc())
        .all()
    )
    meta["days_logged"] = len(rows)

    if len(rows) < 7:
        b = weighted_baseline(user.earnings_json)
        meta["note"] = "Fewer than 7 stored days — using 7-number WMA fallback."
        return b, meta

    # Last 7 calendar entries (most recent 7 days with data)
    last7 = sorted(rows[:7], key=lambda r: r.earn_date)
    amounts7 = [r.amount for r in last7]
    wma7 = sum(w * a for w, a in zip(WEIGHTS, amounts7))

    today_dow = date.today().weekday()
    same_dow = [r.amount for r in rows if r.earn_date.weekday() == today_dow]
    dow_med = float(median(same_dow)) if same_dow else wma7

    # Blend: emphasize weekday pattern (real riders: Mon ≠ Sat)
    blended = 0.42 * dow_med + 0.58 * wma7
    meta.update(
        {
            "method": "blend_dow_wma",
            "data_source": "auto_synthetic_or_stored_daily",
            "dow_median_same_weekday": round(dow_med, 2),
            "wma_last7_logged": round(wma7, 2),
            "blend_weights": "0.42*dow + 0.58*wma",
        }
    )
    return round(blended, 2), meta


def simulate_today_earning(baseline: float, disruption_active: bool) -> float:
    """Demo: under disruption, partner earns far less."""
    if disruption_active:
        return round(baseline * 0.18, 2)
    return baseline


def income_drop_pct(baseline: float, actual: float) -> float:
    if baseline <= 0:
        return 0.0
    return max(0.0, (baseline - actual) / baseline)
