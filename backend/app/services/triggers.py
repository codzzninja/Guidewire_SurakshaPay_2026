"""
Parametric trigger evaluation — dual gate: external disruption + income drop.
Uses real OpenWeather + WAQI + RSS when ALLOW_MOCKS=false (default).
"""

from datetime import date, timedelta
import json
import uuid
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.earning_day import EarningDay
from app.models.event import DisruptionEvent
from app.models.policy import Policy, PolicyStatus
from app.models.user import User
from app.services.baseline import effective_daily_baseline, income_drop_pct, simulate_today_earning
from app.services.fraud import evaluate_claim
from app.services.payouts import initiate_payout
from app.config import settings
from app.services.errors import IntegrationError
from app.services.rss_alerts import fetch_social_rss_signals
from app.services.weather import fetch_all_triggers


def _social_calendar_fallback() -> tuple[bool, bool]:
    """Only used when ALLOW_MOCKS=true and RSS is skipped."""
    d = date.today().toordinal()
    return (d % 11) == 0, (d % 13) == 1


def live_payload_from_env_rss(env: dict[str, Any], rss: dict[str, Any]) -> dict[str, Any]:
    """Build the same response shape as live monitoring from cached env + rss dicts."""
    w = env["weather"]
    a = env["aqi"]
    curfew = bool(rss.get("curfew_social"))
    zone_close = bool(rss.get("traffic_zone_closure"))
    flags: dict[str, bool] = {
        "heavy_rain": bool(w["rain_trigger"]),
        "extreme_heat": bool(w["heat_trigger"]),
        "severe_aqi": bool(a["severe_pollution"]),
        "curfew_social": curfew,
        "traffic_zone_closure": zone_close,
    }
    details: dict[str, Any] = {
        "weather_api": w,
        "aqi_api": a,
        "rss": rss,
    }
    return {"any_external": any(flags.values()), "flags": flags, "details": details}


async def evaluate_external_triggers(lat: float, lon: float, force_mock: bool) -> dict[str, Any]:
    if force_mock:
        flags: dict[str, bool] = {
            "heavy_rain": True,
            "extreme_heat": False,
            "severe_aqi": False,
            "curfew_social": True,
            "traffic_zone_closure": False,
        }
        details = {"mode": "forced_mock_disruption"}
        return {"any_external": True, "flags": flags, "details": details}

    env = await fetch_all_triggers(lat, lon)

    try:
        rss = await fetch_social_rss_signals()
    except IntegrationError:
        if settings.allow_mocks:
            curfew, zone_close = _social_calendar_fallback()
            rss = {
                "curfew_social": curfew,
                "traffic_zone_closure": zone_close,
                "source": "fallback_calendar",
                "note": "RSS not configured",
            }
        else:
            raise
    except Exception as e:
        if settings.allow_mocks:
            curfew, zone_close = _social_calendar_fallback()
            rss = {
                "curfew_social": curfew,
                "traffic_zone_closure": zone_close,
                "source": "fallback_calendar",
                "error": str(e),
            }
        else:
            raise IntegrationError(f"RSS failed: {e}", "rss") from e

    return live_payload_from_env_rss(env, rss)


def payout_formula(income_loss: float, max_per_event: float) -> float:
    return round(min(income_loss * 0.85, max_per_event), 2)


async def run_pipeline_for_user(
    db: Session,
    user: User,
    force_mock_disruption: bool = False,
) -> dict[str, Any]:
    ext = await evaluate_external_triggers(user.lat, user.lon, force_mock_disruption)
    baseline, baseline_meta = effective_daily_baseline(db, user)
    disruption_active = ext["any_external"]
    today_earn = simulate_today_earning(baseline, disruption_active)
    drop = income_drop_pct(baseline, today_earn)

    gate1 = disruption_active
    gate2 = drop > 0.40

    policy = (
        db.query(Policy)
        .filter(
            Policy.user_id == user.id,
            Policy.status == PolicyStatus.active.value,
            Policy.payment_status == "paid",
        )
        .order_by(Policy.id.desc())
        .first()
    )

    result: dict[str, Any] = {
        "user_id": user.id,
        "external": ext,
        "baseline_daily": round(baseline, 2),
        "baseline_detail": baseline_meta,
        "simulated_today_earning": today_earn,
        "income_drop_pct": round(drop, 4),
        "gate1_external": gate1,
        "gate2_income_drop": gate2,
        "dual_gate_open": gate1 and gate2,
        "claim_created": False,
        "message": "",
    }

    if not (user.consent_gps_location and user.consent_upi_account and user.consent_platform_activity):
        result["message"] = "DPDP consent required (GPS, UPI, platform activity) before claim automation"
        result["consent_required"] = True
        return result

    if getattr(user, "kyc_status", "pending") != "verified":
        result["message"] = "KYC verification required before parametric payout"
        result["kyc_required"] = True
        return result

    active_days = (
        db.query(EarningDay)
        .filter(
            EarningDay.user_id == user.id,
            EarningDay.earn_date >= (date.today() - timedelta(days=365)),
            EarningDay.minutes_online.isnot(None),
            EarningDay.minutes_online > 0,
        )
        .count()
    )
    user.active_days_last_365 = int(active_days)
    db.add(user)
    db.flush()
    # Social Security Code proxy gate: minimum engagement for payout eligibility.
    if settings.enforce_min_active_days and active_days < settings.min_active_days_for_payout:
        needed = settings.min_active_days_for_payout
        result["message"] = f"Insufficient active workdays for payout eligibility ({active_days}/{needed})"
        result["eligibility_active_days"] = active_days
        result["min_required_active_days"] = needed
        return result

    if not policy:
        result["message"] = "No paid active weekly policy — pay weekly premium first"
        return result

    if not (gate1 and gate2):
        result["message"] = "Dual-gate not satisfied"
        return result

    # Prevent repeated paid payouts on the same calendar day for a user.
    today_iso = date.today().isoformat()
    already_paid_today = (
        db.query(Claim)
        .filter(
            Claim.user_id == user.id,
            Claim.status == "paid",
            func.date(Claim.created_at) == today_iso,
        )
        .first()
    )
    if already_paid_today:
        result["message"] = "Already paid once today — skipping duplicate payout"
        result["already_paid_today"] = True
        return result

    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    zone_id = user.zone_id
    income_loss = max(0.0, baseline - today_earn)
    fraud = evaluate_claim(
        db,
        user,
        zone_id,
        event_id,
        drop,
        external_details=ext.get("details") if isinstance(ext.get("details"), dict) else None,
        force_mock_disruption=force_mock_disruption,
    )
    result["fraud_msts"] = fraud.msts

    ev = DisruptionEvent(
        event_id=event_id,
        zone_id=zone_id,
        disruption_type=json.dumps(ext["flags"]),
        severity=drop,
        external_confirmed=True,
        raw_payload=json.dumps(ext["details"])[:2000],
    )
    db.add(ev)

    payout_amt = payout_formula(income_loss, policy.max_per_event)
    status = "pending"
    payout_ref = ""

    if fraud.approved and fraud.score < 0.75:
        status = "paid"
        _, payout_ref = initiate_payout(user.upi_id, int(payout_amt * 100), "surakshapay_parametric")
    elif fraud.approved:
        status = "review"
    else:
        status = "rejected"
        payout_amt = 0.0

    active = [k for k, v in ext["flags"].items() if v]
    dtype = active[0] if len(active) == 1 else ("combined:" + ",".join(active[:3]))
    claim = Claim(
        user_id=user.id,
        policy_id=policy.id,
        event_id=event_id,
        disruption_type=dtype[:60],
        income_loss=round(income_loss, 2),
        payout_amount=payout_amt,
        premium_paid_amount=round(float(policy.premium_paid_amount or policy.weekly_premium or 0.0), 2),
        premium_payment_id=(policy.premium_payment_id or "")[:96],
        status=status,
        fraud_score=fraud.score,
        fraud_notes=fraud.notes,
        payout_ref=payout_ref,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    result["claim_created"] = True
    result["claim_id"] = claim.id
    result["payout_amount"] = payout_amt
    result["fraud_score"] = fraud.score
    result["fraud_notes"] = fraud.notes
    result["status"] = status
    result["message"] = "Claim evaluated"
    return result


async def run_pipeline_all_users(db: Session, force_mock: bool) -> list[dict]:
    users = db.query(User).all()
    out = []
    for u in users:
        out.append(await run_pipeline_for_user(db, u, force_mock_disruption=force_mock))
    return out
