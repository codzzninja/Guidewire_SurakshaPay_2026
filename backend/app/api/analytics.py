"""Phase 3 analytics — worker insights + insurer (admin) portfolio view."""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.data.work_zones import ZONE_BY_ID
from app.database import get_db
from app.deps import get_current_user
from app.models.claim import Claim
from app.models.policy import Policy, PolicyStatus
from app.models.user import User
from app.services.baseline import effective_daily_baseline
from app.services.errors import IntegrationError
from app.services.rss_alerts import fetch_social_rss_signals
from app.services.safe_hours import safe_hours_profile
from app.services.weather import fetch_openweather, parametric_week_outlook

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _require_admin_token(x_admin: str | None) -> None:
    # Bypassed for testing purposes as requested. 
    # Any token or no token allowed.
    return


@router.get("/me")
def worker_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    baseline, baseline_meta = effective_daily_baseline(db, user)
    pol = (
        db.query(Policy)
        .filter(Policy.user_id == user.id, Policy.status == PolicyStatus.active.value)
        .order_by(Policy.id.desc())
        .first()
    )
    claims = db.query(Claim).filter(Claim.user_id == user.id).all()
    paid = [c for c in claims if c.status == "paid"]
    payouts_total = sum(c.payout_amount for c in paid)
    premiums_all = db.query(func.coalesce(func.sum(Policy.weekly_premium), 0.0)).filter(Policy.user_id == user.id).scalar()
    coverage_cap = float(pol.max_weekly_coverage) if pol else 0.0
    per_event = float(pol.max_per_event) if pol else None

    ep_headline = (
        f"Earnings protected: ₹{payouts_total:,.0f} transferred across {len(paid)} approved parametric payout(s)."
        if paid
        else "Earnings protected: ₹0 so far — your policy pays when disruption + income-drop gates both pass."
    )
    cov_headline = (
        f"Active weekly coverage — up to {coverage_cap:,.0f} INR this policy week (max {per_event:,.0f} INR per event)."
        if pol
        else "No active weekly policy — subscribe below to lock coverage."
    )

    return {
        "worker": {
            "user_id": user.id,
            "zone_id": user.zone_id,
            "baseline_daily_inr": baseline,
            "baseline_detail": baseline_meta,
            "safe_hours": safe_hours_profile(user.avg_hours_per_day),
        },
        "coverage": {
            "active_weekly": bool(pol),
            "headline": cov_headline,
            "label": "Active weekly coverage" if pol else "No active coverage",
            "plan_type": pol.plan_type if pol else None,
            "weekly_premium_inr": float(pol.weekly_premium) if pol else None,
            "max_weekly_coverage_inr": coverage_cap,
            "max_per_event_inr": per_event,
            "week_window": (
                {"start": pol.week_start.isoformat(), "end": pol.week_end.isoformat()} if pol else None
            ),
        },
        "earnings_protected": {
            "total_parametric_payouts_inr": round(payouts_total, 2),
            "approved_payout_events": len(paid),
            "headline": ep_headline,
        },
        "protection_summary": {
            "claims_total": len(claims),
            "claims_paid": len(paid),
            "total_payouts_inr": round(payouts_total, 2),
            "estimated_premiums_paid_inr": round(float(premiums_all or 0), 2),
            "earnings_protected_narrative": ep_headline,
        },
    }


@router.get("/admin/summary")
async def insurer_admin_summary(
    db: Session = Depends(get_db),
    x_suraksha_admin_token: str | None = Header(None, alias="X-Suraksha-Admin-Token"),
):
    _require_admin_token(x_suraksha_admin_token)

    n_users = db.query(func.count(User.id)).scalar() or 0
    active_policies = (
        db.query(Policy).filter(Policy.status == PolicyStatus.active.value).all()
    )
    prem_pool = sum(float(p.weekly_premium) for p in active_policies)

    claims = db.query(Claim).all()
    by_status: dict[str, int] = {}
    payouts_all_time = 0.0
    for c in claims:
        by_status[c.status] = by_status.get(c.status, 0) + 1
        if c.status == "paid":
            payouts_all_time += float(c.payout_amount)

    since_7d = datetime.now(timezone.utc) - timedelta(days=7)
    now_utc = datetime.now(timezone.utc)

    # Actuarial proxy: Find policies active during the last 7 days to calculate earned premium.
    overlapping_policies = db.query(Policy).filter(
        Policy.week_end >= since_7d, 
        Policy.week_start <= now_utc
    ).all()
    
    earned_premium_7d = 0.0
    for p in overlapping_policies:
        ws = p.week_start
        if not isinstance(ws, datetime):
            ws = datetime(ws.year, ws.month, ws.day, tzinfo=timezone.utc)
        elif not ws.tzinfo:
            ws = ws.replace(tzinfo=timezone.utc)
            
        we = p.week_end
        if not isinstance(we, datetime):
            we = datetime(we.year, we.month, we.day, tzinfo=timezone.utc)
        elif not we.tzinfo:
            we = we.replace(tzinfo=timezone.utc)
            
        start_date = max(ws, since_7d)
        end_date = min(we, now_utc)
        overlap_days = (end_date - start_date).total_seconds() / 86400.0
        if overlap_days > 0:
            earned_premium_7d += float(p.weekly_premium) * (overlap_days / 7.0)

    paid_last_7d = (
        db.query(Claim)
        .filter(Claim.status == "paid", Claim.created_at >= since_7d)
        .all()
    )
    payouts_7d = sum(float(c.payout_amount) for c in paid_last_7d)

    # Actuarial proxy: Earned premium vs incurred loss proxy
    loss_ratio = payouts_7d / max(earned_premium_7d, 1.0) if earned_premium_7d > 0.1 else None
    
    # All-time proxy: Total paid vs total premium issued ever
    all_time_policies = db.query(Policy).all()
    issued_premium_all_time = sum(float(p.weekly_premium) for p in all_time_policies)
    loss_ratio_all_time = payouts_all_time / max(issued_premium_all_time, 1.0) if issued_premium_all_time > 0.1 else None

    zone_rows = (
        db.query(User.zone_id, func.count(User.id))
        .group_by(User.zone_id)
        .order_by(func.count(User.id).desc())
        .limit(25)
        .all()
    )
    zone_distribution = [{"zone_id": z, "workers": n} for z, n in zone_rows]

    nowcast, week_ahead = await _portfolio_weather_outlooks(db)
    social = await _insurer_social_signals_safe()
    week_ahead = _enrich_predictive_with_social_rss(week_ahead, social)
    week_ahead = _add_predicted_claim_activity(week_ahead, db, len(active_policies))
    prediction_center = _build_admin_prediction_center(week_ahead, db, prem_pool)

    return {
        "portfolio": {
            "registered_workers": n_users,
            "active_policies": len(active_policies),
            "weekly_premium_pool_inr": round(prem_pool, 2),
            "claims_by_status": by_status,
            "paid_payouts_last_7d_inr": round(payouts_7d, 2),
            "paid_claim_count_last_7d": len(paid_last_7d),
            "total_paid_payouts_all_time_inr": round(payouts_all_time, 2),
            # Same as all-time total — kept for older clients
            "total_paid_payouts_inr": round(payouts_all_time, 2),
            "loss_ratio": {
                "ratio": round(loss_ratio, 4) if loss_ratio is not None else None,
                "as_percent": round(loss_ratio * 100, 2) if loss_ratio is not None else None,
                "numerator_paid_claims_inr": round(payouts_7d, 2),
                "denominator_active_weekly_premium_pool_inr": round(prem_pool, 2),
                "window": "rolling_7d_paid_claims_vs_weekly_premium_pool",
                "basis": (
                    "Illustrative: **paid claim amounts in the last 7 days** ÷ **sum of weekly premiums** for "
                    "currently active policies (one-week premium run-rate). Same time horizon for a clean read — "
                    "not statutory loss ratio."
                ),
            },
            "loss_ratio_all_time": {
                "ratio": round(loss_ratio_all_time, 4) if loss_ratio_all_time is not None else None,
                "as_percent": round(loss_ratio_all_time * 100, 2)
                if loss_ratio_all_time is not None
                else None,
                "numerator_total_paid_claims_inr": round(payouts_all_time, 2),
                "denominator_active_weekly_premium_pool_inr": round(prem_pool, 2),
                "basis": (
                    "Legacy view: all-time paid claim amounts ÷ same weekly premium pool (denominator unchanged)."
                ),
            },
        },
        "zones_top": zone_distribution,
        "environment_nowcast_24h": nowcast,
        "predictive_week_ahead_disruption": week_ahead,
        "admin_prediction_center": prediction_center,
    }


def _top_zone_anchors_by_workers(db: Session, limit: int) -> list[tuple[str, float, float, int]]:
    """(zone_id, lat, lon, worker_count) for known zone centroids, highest headcount first."""
    rows = (
        db.query(User.zone_id, func.count(User.id))
        .group_by(User.zone_id)
        .order_by(func.count(User.id).desc())
        .limit(limit * 2)
        .all()
    )
    out: list[tuple[str, float, float, int]] = []
    for zone_id, n in rows:
        z = ZONE_BY_ID.get(zone_id)
        if z:
            out.append((zone_id, float(z["lat"]), float(z["lon"]), int(n)))
        if len(out) >= limit:
            break
    return out


async def _fetch_one_market_weather(
    zone_id: str,
    lat: float,
    lon: float,
    worker_count: int,
) -> dict[str, Any]:
    """Live nowcast + week-ahead for one work-zone centroid."""
    try:
        w, pw = await asyncio.gather(
            fetch_openweather(lat, lon),
            parametric_week_outlook(lat, lon),
        )
    except Exception as e:  # noqa: BLE001
        return {
            "zone_id": zone_id,
            "worker_count": worker_count,
            "anchor": {"lat": lat, "lon": lon},
            "error": str(e),
        }
    return {
        "zone_id": zone_id,
        "worker_count": worker_count,
        "anchor": {"lat": lat, "lon": lon},
        "nowcast_24h": {
            "forecast_rain_24h_mm": w.forecast_rain_24h_mm,
            "max_temp_next_24h_c": w.max_temp_next_24h,
            "rain_trigger_now": w.rain_trigger,
            "heat_trigger_now": w.heat_trigger,
            "narrative_24h": _outlook_narrative(w),
        },
        "week_ahead": pw,
    }


async def _portfolio_weather_outlooks(db: Session) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Generic portfolio view: sample forecasts at **top work zones by registered workers**
    (not a single hard-coded city). Falls back to DEFAULT_CITY_* only if no known zones.
    """
    cap = max(1, min(20, settings.insurer_weather_max_markets))
    anchors = _top_zone_anchors_by_workers(db, cap)

    if not anchors:
        try:
            w = await fetch_openweather(settings.default_city_lat, settings.default_city_lon)
            pw = await parametric_week_outlook(settings.default_city_lat, settings.default_city_lon)
        except Exception as e:  # noqa: BLE001
            err = {"error": str(e), "narrative_24h": "Weather unavailable."}
            return err, {"error": str(e), "summary": {"insurer_narrative": "Week-ahead unavailable."}}
        single = {
            "mode": "fallback_single_anchor",
            "reason": "No users registered in known work zones — using DEFAULT_CITY_LAT/LON from config.",
            "markets": [
                {
                    "zone_id": "_config_default",
                    "worker_count": 0,
                    "anchor": {"lat": settings.default_city_lat, "lon": settings.default_city_lon},
                    "nowcast_24h": {
                        "forecast_rain_24h_mm": w.forecast_rain_24h_mm,
                        "max_temp_next_24h_c": w.max_temp_next_24h,
                        "rain_trigger_now": w.rain_trigger,
                        "heat_trigger_now": w.heat_trigger,
                        "narrative_24h": _outlook_narrative(w),
                    },
                    "week_ahead": pw,
                }
            ],
            "rollup_24h": {
                "markets_sampled": 1,
                "summary_line": "Single fallback anchor — add users with standard zone IDs for multi-market view.",
            },
            "rollup_week": pw.get("summary", {}),
        }
        pw_sum = pw.get("summary") or {}
        week_wrap = {
            "mode": "fallback_single_anchor",
            "reason": single["reason"],
            "markets": [
                {
                    "zone_id": "_config_default",
                    "worker_count": 0,
                    "anchor": {"lat": settings.default_city_lat, "lon": settings.default_city_lon},
                    "source": pw.get("source"),
                    "days": pw.get("days"),
                    "summary": pw.get("summary"),
                }
            ],
            "rollup": {
                **pw_sum,
                "summary_line": pw_sum.get("insurer_narrative", "Week-ahead from fallback anchor."),
            },
        }
        return single, week_wrap

    markets = await asyncio.gather(
        *[_fetch_one_market_weather(zid, la, lo, wc) for zid, la, lo, wc in anchors]
    )

    ok_now = [m for m in markets if "error" not in m]
    err_mk = [m for m in markets if "error" in m]

    if not ok_now:
        return {
            "mode": "portfolio_all_markets_failed",
            "description": "All sampled markets failed to fetch weather — check OPENWEATHER_API_KEY and quotas.",
            "markets": [{"zone_id": m.get("zone_id"), "error": m.get("error")} for m in markets],
            "rollup_24h": {"summary_line": "No successful nowcast — see per-market errors."},
        }, {
            "mode": "portfolio_all_markets_failed",
            "markets": [],
            "rollup": {"summary_line": "No week-ahead data."},
        }

    tw = sum(m["worker_count"] for m in ok_now) or 1
    w_rain = sum(
        float(m["nowcast_24h"]["forecast_rain_24h_mm"]) * m["worker_count"] for m in ok_now
    ) / tw
    rain_on = sum(1 for m in ok_now if m["nowcast_24h"]["rain_trigger_now"])
    heat_on = sum(1 for m in ok_now if m["nowcast_24h"]["heat_trigger_now"])

    nowcast = {
        "mode": "portfolio_by_registered_zones",
        "description": (
            "Forecasts sampled at work-zone centroids with the most registered workers "
            f"(up to {cap} markets). Weighted by headcount where noted."
        ),
        "markets": [
            {
                "zone_id": m["zone_id"],
                "worker_count": m["worker_count"],
                "anchor": m["anchor"],
                **(
                    m["nowcast_24h"]
                    if "nowcast_24h" in m
                    else {"error": m.get("error", "unknown")}
                ),
            }
            for m in markets
        ],
        "rollup_24h": {
            "markets_sampled": len(ok_now),
            "markets_failed": len(err_mk),
            "total_workers_represented": sum(m["worker_count"] for m in ok_now),
            "worker_weighted_mean_rain_24h_mm": round(w_rain, 2),
            "share_of_markets_with_rain_trigger": round(rain_on / max(len(ok_now), 1), 3),
            "share_of_markets_with_heat_trigger": round(heat_on / max(len(ok_now), 1), 3),
            "summary_line": (
                f"Across {len(ok_now)} zone(s) covering {sum(m['worker_count'] for m in ok_now)} worker registration(s): "
                f"weighted-mean 24h rain ≈ {w_rain:.1f} mm; "
                f"{rain_on}/{len(ok_now)} markets show rain-trigger band; "
                f"{heat_on}/{len(ok_now)} show heat-trigger band."
            ),
        },
    }

    ok_week = [m for m in markets if "week_ahead" in m and "error" not in m]
    pressures = []
    elevated = []
    for m in ok_week:
        s = (m.get("week_ahead") or {}).get("summary") or {}
        if isinstance(s, dict) and s.get("mean_disruption_pressure") is not None:
            pressures.append(float(s["mean_disruption_pressure"]) * m["worker_count"])
            elevated.append(int(s.get("elevated_disruption_days") or 0) * m["worker_count"])
    tw2 = sum(m["worker_count"] for m in ok_week) or 1
    mean_p = sum(pressures) / tw2 if pressures else None
    elevated_w = sum(elevated) / tw2 if elevated else None

    week_ahead = {
        "mode": "portfolio_by_registered_zones",
        "description": nowcast["description"],
        "markets": [
            {
                "zone_id": m["zone_id"],
                "worker_count": m["worker_count"],
                "anchor": m["anchor"],
                "source": (m.get("week_ahead") or {}).get("source"),
                "days": (m.get("week_ahead") or {}).get("days"),
                "summary": (m.get("week_ahead") or {}).get("summary"),
            }
            for m in markets
            if "week_ahead" in m
        ],
        "rollup": {
            "worker_weighted_mean_disruption_pressure": round(mean_p, 4) if mean_p is not None else None,
            "worker_weighted_mean_elevated_days": round(elevated_w, 3) if elevated_w is not None else None,
            "summary_line": (
                (
                    f"Portfolio week-ahead: worker-weighted mean disruption pressure ≈ {mean_p:.3f} "
                    f"(higher → more environmental stress vs trigger bands). "
                    f"Typical elevated-risk days/week across markets (worker-weighted): ≈ {elevated_w:.2f}."
                )
                if mean_p is not None
                else "Week-ahead rollup unavailable — check per-market errors."
            ),
        },
    }

    return nowcast, week_ahead


async def _insurer_social_signals_safe() -> dict[str, Any]:
    """RSS / social-style disruption flags — never fails the admin endpoint."""
    try:
        return await fetch_social_rss_signals()
    except IntegrationError as e:
        if settings.allow_mocks:
            return {
                "curfew_social": False,
                "traffic_zone_closure": False,
                "source": "skipped_allow_mocks",
                "note": str(e),
            }
        return {
            "curfew_social": False,
            "traffic_zone_closure": False,
            "source": "error",
            "error": str(e),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "curfew_social": False,
            "traffic_zone_closure": False,
            "source": "error",
            "error": str(e),
        }


def _enrich_predictive_with_social_rss(week_ahead: dict[str, Any], social: dict[str, Any]) -> dict[str, Any]:
    """
    Merge ReliefWeb-style RSS scan with weather-only week scores.
    Social is national/feed-level (not per day); weather is per zone × day.
    """
    rollup = week_ahead.get("rollup")
    if not isinstance(rollup, dict):
        rollup = {}
        week_ahead["rollup"] = rollup

    mean_p = rollup.get("worker_weighted_mean_disruption_pressure")
    curfew = bool(social.get("curfew_social"))
    closure = bool(social.get("traffic_zone_closure"))
    
    # Multiplicative shock factors based on external constraints
    curfew_mult = 1.4 if curfew else 1.0
    closure_mult = 1.2 if closure else 1.0
    total_mult = curfew_mult * closure_mult
    
    if mean_p is not None:
        combined = float(min(1.0, float(mean_p) * total_mult))
        social_add = max(0.0, combined - float(mean_p))
    else:
        combined = float(min(1.0, 0.3 * total_mult)) if (curfew or closure) else None
        social_add = combined if combined else 0.0

    week_ahead["social_disruption_feed"] = {
        "curfew_social": curfew,
        "traffic_zone_closure": closure,
        "feed_title": social.get("feed_title"),
        "rss_source": social.get("source"),
        "keyword_matches": social.get("matches") or [],
        "explain": (
            "Scan of configured RSS (e.g. ReliefWeb India) for curfew / strike / closure language. "
            "Applies as a portfolio-wide overlay — not mapped to individual calendar days."
        ),
    }

    rollup["weather_only_mean_pressure_0_1"] = mean_p
    rollup["social_overlay_addition_0_1"] = round(social_add, 4)
    rollup["combined_external_eval_pressure_0_1"] = round(combined, 4) if combined is not None else None
    _old_elev = rollup.pop("worker_weighted_mean_elevated_days", None)
    if _old_elev is not None:
        rollup["avg_elevated_weather_days_per_market_weighted"] = _old_elev

    rollup["what_this_predicts"] = (
        "Indices show **external trigger strength** (weather + RSS). A separate **claim-activity estimate** below blends "
        "this with **recent claim filing rates** — illustrative expected **new claim records** next 7 days, not paid rupees. "
        "Approvals still need dual-gate + fraud."
    )

    parts_w = []
    if mean_p is not None:
        parts_w.append(f"Weather stress index (worker-weighted across zones) ≈ {float(mean_p):.3f}.")
    parts_s = []
    if curfew:
        parts_s.append("RSS suggests curfew / social-order style keywords in recent headlines.")
    if closure:
        parts_s.append("RSS suggests closures / bandh / traffic disruption keywords.")
    if not parts_s and social.get("source") not in ("error", "skipped_allow_mocks"):
        parts_s.append("No strong curfew/closure keywords in the current RSS window.")
    if social.get("error"):
        parts_s.append(f"RSS fetch issue: {social.get('error')}")

    rollup["headline_combined"] = " ".join(parts_w + parts_s).strip() or (
        "Weather and social feeds loaded — see per-zone tables for day-level weather stress."
    )

    # Shorter legacy line for older clients
    rollup["summary_line"] = rollup["headline_combined"]

    return week_ahead


def _zone_mean_pressure_from_market(m: dict[str, Any]) -> float:
    s = m.get("summary") if isinstance(m.get("summary"), dict) else {}
    mp = s.get("mean_disruption_pressure")
    if mp is not None:
        return float(mp)
    days = m.get("days")
    if isinstance(days, list) and days:
        vals = []
        for d in days:
            if isinstance(d, dict) and d.get("disruption_pressure_0_1") is not None:
                vals.append(float(d["disruption_pressure_0_1"]))
        if vals:
            return float(sum(vals) / len(vals))
    return 0.0


def _claim_forecast_methodology_text() -> str:
    return (
        "For each work zone: **weekly claim filing rate** estimated from **last-14-days** claims tagged to users in "
        "that zone (or worker-weighted share of portfolio filings if thin). Multiplied by **zone weather pressure** "
        "from forecast buckets + the **same RSS overlay** applied everywhere. **Sum = portfolio total** — illustrative "
        "new claim records next ~7 days, not payout ₹. Production would use GLM / experience rating."
    )


def _zone_disruption_risk_tier(combined_pressure_0_1: float) -> tuple[str, int]:
    """Human-readable tier + 0–100 score for admin UI (pressure-driven, not actuarial)."""
    cp = float(min(1.0, max(0.0, combined_pressure_0_1)))
    score = int(round(cp * 100))
    if cp >= 0.55:
        return "critical", score
    if cp >= 0.38:
        return "high", score
    if cp >= 0.22:
        return "moderate", score
    return "low", score


def _suggest_weekly_premium_delta_pct(combined_pressure_0_1: float) -> float:
    """Illustrative dynamic-pricing nudge vs baseline week (demo only)."""
    cp = float(min(1.0, max(0.0, combined_pressure_0_1)))
    raw = (cp - 0.2) * 22.0
    return float(round(max(-6.0, min(18.0, raw)), 1))


def _aggregate_high_risk_forecast_days(markets: list[dict[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
    """Cross-zone max disruption pressure per calendar day → watchlist for ops."""
    by_date: dict[str, list[tuple[str, float]]] = {}
    for m in markets:
        if not isinstance(m, dict):
            continue
        zid = str(m.get("zone_id") or "")
        if not zid or zid.startswith("_config"):
            continue
        days = m.get("days")
        if not isinstance(days, list):
            continue
        for d in days:
            if not isinstance(d, dict):
                continue
            ds = d.get("date")
            if ds is None:
                continue
            p = d.get("disruption_pressure_0_1")
            if p is None:
                continue
            key = str(ds)
            by_date.setdefault(key, []).append((zid, float(p)))

    rows: list[dict[str, Any]] = []
    for date_s, zlist in by_date.items():
        mx = max(zlist, key=lambda x: x[1])
        zones_hot = sum(1 for _z, pv in zlist if pv >= 0.28)
        rows.append(
            {
                "date": date_s,
                "max_disruption_pressure_0_1": round(mx[1], 4),
                "worst_zone_id": mx[0],
                "zones_above_elevated_threshold": zones_hot,
            }
        )
    rows.sort(key=lambda r: float(r["max_disruption_pressure_0_1"]), reverse=True)
    return rows[:top_n]


def _build_admin_prediction_center(
    week_ahead: dict[str, Any],
    db: Session,
    weekly_premium_pool_inr: float,
) -> dict[str, Any]:
    """
    Rich admin bundle: payout illustration, risk ranking, calendar peaks, what-if, fraud snapshot.
    All figures are **illustrative** for dashboards / hackathon judging.
    """
    rollup = week_ahead.get("rollup") if isinstance(week_ahead.get("rollup"), dict) else {}
    markets = week_ahead.get("markets")
    markets_list = [m for m in (markets if isinstance(markets, list) else []) if isinstance(m, dict)]

    sf = (
        week_ahead.get("social_disruption_feed")
        if isinstance(week_ahead.get("social_disruption_feed"), dict)
        else {}
    )
    curfew_b = bool(sf.get("curfew_social"))
    closure_b = bool(sf.get("traffic_zone_closure"))
    curfew_mult = 1.4 if curfew_b else 1.0
    closure_mult = 1.2 if closure_b else 1.0
    total_mult = curfew_mult * closure_mult
    
    mean_w = rollup.get("weather_only_mean_pressure_0_1")
    mean_f = float(mean_w) if mean_w is not None else None
    
    social_add = max(0.0, min(1.0, mean_f * total_mult) - mean_f) if (mean_f is not None and (curfew_b or closure_b)) else ((0.14 if curfew_b else 0.0) + (0.12 if closure_b else 0.0))
    
    combined_now = rollup.get("combined_external_eval_pressure_0_1")
    comb_f = float(combined_now) if combined_now is not None else None

    what_if: dict[str, Any] = {
        "label": "Scenario stress (portfolio index)",
        "weather_only_pressure_0_1": round(mean_f, 4) if mean_f is not None else None,
        "rss_overlay_addition_0_1": round(social_add, 4),
        "if_rss_overlay_removed_pressure_0_1": round(mean_f, 4) if mean_f is not None else None,
        "if_rss_overlay_max_stress_pressure_0_1": (
            round(min(1.0, mean_f + 0.26), 4) if mean_f is not None else None
        ),
        "note": (
            "RSS overlay is national — not mapped to calendar days. "
            "'Max stress' adds +0.26 as a rough upper envelope for demo what-if."
        ),
    }

    high_days = _aggregate_high_risk_forecast_days(markets_list, top_n=6)

    paid_rows = (
        db.query(Claim.payout_amount)
        .filter(Claim.status == "paid", Claim.payout_amount > 0)
        .all()
    )
    paid_amts = [float(r[0]) for r in paid_rows]
    avg_paid = float(sum(paid_amts) / len(paid_amts)) if paid_amts else 420.0

    since30 = datetime.now(timezone.utc) - timedelta(days=30)
    recent_claims = db.query(Claim).filter(Claim.created_at >= since30).all()
    n_recent = len(recent_claims)
    avg_fraud_30d = (
        round(sum(c.fraud_score for c in recent_claims) / n_recent, 4) if n_recent else None
    )
    fraud_review = sum(
        1 for c in recent_claims if c.status == "pending" and float(c.fraud_score) >= 0.75
    )
    fraud_high = sum(1 for c in recent_claims if float(c.fraud_score) >= 0.75)

    block = week_ahead.get("predicted_claim_activity_next_7d")
    total_events = None
    if isinstance(block, dict):
        te = block.get("portfolio_total_new_claim_events")
        if te is None:
            te = block.get("illustrative_expected_new_claim_events")
        total_events = float(te) if te is not None else None

    payout_est = None
    loss_cost_to_premium = None
    capital_buffer_inr = None
    if total_events is not None:
        payout_est = round(total_events * avg_paid, 2)
        pool = max(float(weekly_premium_pool_inr), 1.0)
        loss_cost_to_premium = round(payout_est / pool, 4)
        capital_buffer_inr = round(payout_est * 1.2, 2)

    by_zone = (block or {}).get("by_zone") if isinstance(block, dict) else []
    by_zone_list = [z for z in by_zone if isinstance(z, dict)]

    anchor_by_zone = {
        str(m.get("zone_id")): m.get("anchor")
        for m in markets_list
        if m.get("zone_id") and not str(m.get("zone_id")).startswith("_config")
    }

    ranked: list[dict[str, Any]] = []
    for z in by_zone_list:
        zid = str(z.get("zone_id") or "")
        ranked.append(
            {
                **z,
                "anchor": anchor_by_zone.get(zid),
                "rank_score": float(z.get("combined_external_pressure_0_1") or 0)
                + 0.01 * float(z.get("illustrative_expected_new_claim_events_next_7d") or 0),
            }
        )
    ranked.sort(key=lambda r: float(r.get("rank_score") or 0), reverse=True)
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
        r.pop("rank_score", None)

    watchlist = [str(r.get("zone_id")) for r in ranked[:5] if r.get("zone_id")]

    if isinstance(week_ahead.get("predicted_claim_activity_next_7d"), dict):
        b = week_ahead["predicted_claim_activity_next_7d"]
        b["illustrative_avg_paid_claim_inr"] = round(avg_paid, 2)
        if payout_est is not None:
            b["illustrative_expected_payout_inr_next_7d"] = payout_est
        if loss_cost_to_premium is not None:
            b["illustrative_loss_cost_to_weekly_premium_ratio"] = loss_cost_to_premium
        if capital_buffer_inr is not None:
            b["illustrative_capital_buffer_inr_next_7d"] = capital_buffer_inr

    headline_parts = []
    if comb_f is not None:
        headline_parts.append(f"Combined external pressure ≈ {comb_f:.2f}.")
    if total_events is not None:
        headline_parts.append(f"Illustrative ~{total_events:g} new claim events next week.")
    if payout_est is not None:
        headline_parts.append(f"Rough payout load ~₹{payout_est:,.0f} if paid claims match historical average size.")
    if fraud_review:
        headline_parts.append(f"{fraud_review} pending claim(s) in manual fraud review (30d).")

    return {
        "headline": " ".join(headline_parts).strip() or "Prediction center — load portfolio data for full signals.",
        "illustrative_avg_paid_claim_inr": round(avg_paid, 2),
        "illustrative_avg_paid_claim_sample_size": len(paid_amts),
        "illustrative_expected_payout_inr_next_7d": payout_est,
        "illustrative_expected_loss_cost_to_weekly_premium_ratio": loss_cost_to_premium,
        "illustrative_capital_buffer_inr_next_7d": capital_buffer_inr,
        "high_risk_forecast_days": high_days,
        "zones_ranked_by_combined_risk": ranked,
        "stress_watchlist_zone_ids": watchlist,
        "what_if_scenarios": what_if,
        "fraud_portfolio_snapshot_30d": {
            "claims_in_window": n_recent,
            "mean_fraud_score": avg_fraud_30d,
            "claims_pending_fraud_review_gte_075": fraud_review,
            "claims_any_status_fraud_gte_075": fraud_high,
            "note": "Isolation-style scores from claim intake — not a production SIU dashboard.",
        },
        "methodology_blurb": (
            "Bundle joins **weather/RSS pressure**, **per-zone claim activity heuristic**, **historical paid severity**, "
            "and **fraud score distribution**. Numbers are for **admin storytelling** — replace with credentialed pricing "
            "and reserving in production."
        ),
    }


def _add_predicted_claim_activity(
    week_ahead: dict[str, Any],
    db: Session,
    active_policies: int,
) -> dict[str, Any]:
    """
    Per-zone claim-activity estimate → sum to portfolio total.

    Each zone: local weather stress + same RSS overlay + zone's share of recent filings.
    """
    rollup = week_ahead.setdefault("rollup", {})
    sf = (
        week_ahead.get("social_disruption_feed")
        if isinstance(week_ahead.get("social_disruption_feed"), dict)
        else {}
    )
    curfew_b = bool(sf.get("curfew_social"))
    closure_b = bool(sf.get("traffic_zone_closure"))
    total_mult = (1.4 if curfew_b else 1.0) * (1.2 if closure_b else 1.0)

    since = datetime.now(timezone.utc) - timedelta(days=14)
    n_recent_total = (
        db.query(func.count(Claim.id)).filter(Claim.created_at >= since).scalar() or 0
    )
    portfolio_hist_per_week = float(n_recent_total) / 2.0

    zone_hist_rows = (
        db.query(User.zone_id, func.count(Claim.id))
        .join(Claim, Claim.user_id == User.id)
        .filter(Claim.created_at >= since)
        .group_by(User.zone_id)
        .all()
    )
    hist_by_zone: dict[str, float] = {str(z): float(n) / 2.0 for z, n in zone_hist_rows}

    worker_rows = db.query(User.zone_id, func.count(User.id)).group_by(User.zone_id).all()
    workers_by_zone: dict[str, int] = {str(z): int(c) for z, c in worker_rows}
    total_workers = sum(workers_by_zone.values()) or 1

    markets = week_ahead.get("markets")
    if not isinstance(markets, list) or not markets:
        combined = rollup.get("combined_external_eval_pressure_0_1")
        if combined is None:
            combined = rollup.get("weather_only_mean_pressure_0_1")
        cp = float(combined) if combined is not None else 0.0
        hist_per_week = portfolio_hist_per_week
        if hist_per_week < 0.2:
            hist_per_week = 0.25 + 0.06 * float(min(active_policies, 12))
        # GLM Poisson Estimator Proxy
        forward_poisson_exp = math.exp(2.5 * float(cp))
        estimate = max(
            0.0,
            round(
                hist_per_week
                * forward_poisson_exp
                * (0.35 + 0.05 * max(1.0, float(active_policies) ** 0.45)),
                2,
            ),
        )
        band = "low"
        if estimate >= 3.5 or cp >= 0.52:
            band = "elevated"
        elif estimate >= 1.2 or cp >= 0.26:
            band = "moderate"
        block = {
            "band_next_7d": band,
            "illustrative_expected_new_claim_events": estimate,
            "portfolio_total_new_claim_events": estimate,
            "by_zone": [],
            "historical_claims_per_week_baseline": round(hist_per_week, 3),
            "forward_pressure_multiplier": round(forward_poisson_exp, 4),
            "external_pressure_used_0_1": round(cp, 4),
            "disruption_risk_tier": _zone_disruption_risk_tier(float(cp))[0],
            "composite_risk_score_0_100": _zone_disruption_risk_tier(float(cp))[1],
            "suggested_weekly_premium_delta_pct": _suggest_weekly_premium_delta_pct(float(cp)),
            "methodology": _claim_forecast_methodology_text(),
        }
        week_ahead["predicted_claim_activity_next_7d"] = block
        hf = (
            f"Claim-activity forecast (next ~7d): **{band}** — illustrative **~{estimate:g}** new claim events "
            f"(single-baseline fallback — add users in known zones for per-zone breakdown)."
        )
        rollup["headline_claim_forecast"] = hf
        rollup["headline_combined"] = f"{rollup.get('headline_combined', '').strip()} {hf}".strip()
        rollup["summary_line"] = rollup["headline_combined"]
        return week_ahead

    by_zone: list[dict[str, Any]] = []
    total_est = 0.0

    for m in markets:
        if not isinstance(m, dict):
            continue
        zid = str(m.get("zone_id") or "")
        if not zid or zid.startswith("_config"):
            continue
        wc = int(m.get("worker_count") or 0)
        cp_z = _zone_mean_pressure_from_market(m)
        combined_z = float(min(1.0, cp_z * total_mult))

        hist_z = hist_by_zone.get(zid)
        if hist_z is None or hist_z < 0.03:
            share = wc / total_workers if wc else 1.0 / max(len(markets), 1)
            hist_z = (
                portfolio_hist_per_week * share
                if portfolio_hist_per_week > 0
                else 0.12 + 0.045 * float(min(wc, 10))
            )
        if hist_z < 0.08:
            hist_z = 0.08 + 0.02 * float(min(wc, 8))

        # GLM Poisson Estimator Proxy per zone
        forward_poisson_exp_z = math.exp(2.5 * combined_z)
        est_z = max(0.0, hist_z * forward_poisson_exp_z * (0.38 + 0.04 * float(wc**0.5)))
        est_z = round(est_z, 3)
        total_est += est_z

        zb = "low"
        if est_z >= 1.2 or combined_z >= 0.52:
            zb = "elevated"
        elif est_z >= 0.35 or combined_z >= 0.26:
            zb = "moderate"

        risk_tier, risk_score = _zone_disruption_risk_tier(combined_z)
        prem_delta = _suggest_weekly_premium_delta_pct(combined_z)

        by_zone.append(
            {
                "zone_id": zid,
                "workers": wc,
                "weather_mean_pressure_0_1": round(cp_z, 4),
                "combined_external_pressure_0_1": round(combined_z, 4),
                "disruption_risk_tier": risk_tier,
                "composite_risk_score_0_100": risk_score,
                "suggested_weekly_premium_delta_pct": prem_delta,
                "historical_claims_per_week_in_zone": round(hist_z, 4),
                "forward_pressure_multiplier": round(forward_poisson_exp_z, 4),
                "illustrative_expected_new_claim_events_next_7d": est_z,
                "band_next_7d": zb,
            }
        )

    total_est_r = round(total_est, 2)
    cp_port = float(rollup.get("combined_external_eval_pressure_0_1") or 0.0)

    band = "low"
    if total_est_r >= 3.5 or cp_port >= 0.52:
        band = "elevated"
    elif total_est_r >= 1.2 or cp_port >= 0.26:
        band = "moderate"

    block = {
        "band_next_7d": band,
        "illustrative_expected_new_claim_events": total_est_r,
        "portfolio_total_new_claim_events": total_est_r,
        "by_zone": by_zone,
        "portfolio_historical_claims_per_week": round(portfolio_hist_per_week, 4),
        "methodology": _claim_forecast_methodology_text(),
    }
    week_ahead["predicted_claim_activity_next_7d"] = block

    parts = [
        f"{z['zone_id']}: ~{z['illustrative_expected_new_claim_events_next_7d']}" for z in by_zone
    ]
    hf = (
        f"Claim-activity (next ~7d): **{band}** — portfolio total illustrative **~{total_est_r:g}** new events "
        f"({' + '.join(parts)})."
    )
    rollup["headline_claim_forecast"] = hf
    rollup["headline_combined"] = f"{rollup.get('headline_combined', '').strip()} {hf}".strip()
    rollup["summary_line"] = rollup["headline_combined"]

    return week_ahead


def _outlook_narrative(w: Any) -> str:
    parts = []
    if w.forecast_rain_24h_mm >= 45:
        parts.append("Elevated rainfall in the next 24h — expect higher parametric rain exposure.")
    elif w.rain_trigger:
        parts.append("Rain triggers are already active at the anchor coordinates.")
    if w.max_temp_next_24h >= 40:
        parts.append("Heat stress likely — watch heat-index triggers for outdoor gig workers.")
    if not parts:
        parts.append("Environmental triggers near typical bands for the anchor city this cycle.")
    return " ".join(parts)
