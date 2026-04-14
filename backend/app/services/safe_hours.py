"""Safe-hour guidance (Phase 3) — lightweight heuristic aligned with README logistic-regression story."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any


def _ist_now() -> tuple[datetime, int]:
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(timezone.utc).astimezone(ist)
    return now, now.hour


def safe_hours_profile(avg_hours_per_day: float) -> dict[str, Any]:
    """
    Returns a worker-facing window and a 0..1 safety score for the current IST hour.
    Not a trained classifier — demo-grade prior for dashboards / notifications.
    """
    _, hour = _ist_now()
    h = max(0.0, min(14.0, float(avg_hours_per_day or 8.0)))

    # Midday heat + air-quality stress band (typical gig peak conflict).
    heat_band = 1.0 if 11 <= hour <= 16 else 0.0
    late_night = 1.0 if hour < 5 or hour >= 23 else 0.0

    # Logistic-style squash (interpretable coefficients).
    linear = 0.55 + 0.035 * h - 0.22 * heat_band - 0.18 * late_night
    score = 1.0 / (1.0 + math.exp(-linear))
    score = round(max(0.12, min(0.94, score)), 3)

    return {
        "current_hour_ist": hour,
        "safe_score_now": score,
        "recommended_window_local": "06:00–22:00 IST",
        "caution_windows_local": ["11:00–16:00 IST (heat peak)", "23:00–05:00 IST (low visibility)"],
        "avg_hours_per_day_assumed": round(h, 1),
        "model": "heuristic_logistic_proxy",
    }
