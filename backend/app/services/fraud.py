"""
Fraud + adversarial GPS defense (Phase 2–3).

- Layer 1: geographic zone vs claimed work area (per-zone radius, sub-city hubs)
- Layer 2: duplicate paid claim per event + claim velocity
- Layer 3: Isolation Forest on engineered features
- Layer 4: MSTS — movement, noise, teleport, swarm
- Layer 5: weather flag/metric integrity + rolling env history (anti fake-weather path)
- Layer 6: individual vs zone-peer earning volatility
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean, median, pstdev
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.data.work_zones import ZONE_BY_ID, zone_radius_km
from app.models.claim import Claim
from app.models.earning_day import EarningDay
from app.models.user import User
from app.services.environment_cache import load_weather_history

# --- Isolation Forest: synthetic in-distribution vectors (10-D Phase 3) ---
_rng = np.random.RandomState(42)
_N = 5000
_X_train = np.column_stack(
    [
        _rng.uniform(0.0, 0.35, _N),
        _rng.uniform(0.0, 0.35, _N),
        _rng.uniform(0.0, 0.25, _N),
        _rng.uniform(0.15, 0.95, _N),
        _rng.uniform(0.42, 0.92, _N),
        _rng.uniform(0.0, 0.12, _N),
        _rng.uniform(0.0, 0.35, _N),
        _rng.uniform(0.0, 0.25, _N),
        _rng.uniform(0.0, 0.45, _N),
        _rng.uniform(0.0, 0.40, _N),
    ]
)
_ISO = IsolationForest(contamination=0.07, random_state=42, n_estimators=220)
_ISO.fit(_X_train)


@dataclass
class FraudResult:
    score: float
    notes: str
    approved: bool
    msts: dict[str, Any]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def coords_match_claimed_zone(lat: float, lon: float, zone_id: str) -> tuple[bool, float]:
    z = ZONE_BY_ID.get(zone_id)
    if not z:
        return False, 999.0
    d = haversine_km(lat, lon, z["lat"], z["lon"])
    return d <= zone_radius_km(zone_id), d


def duplicate_event(db: Session, user_id: int, event_id: str) -> bool:
    exists = (
        db.query(Claim)
        .filter(Claim.user_id == user_id, Claim.event_id == event_id, Claim.status == "paid")
        .first()
    )
    return exists is not None


def _recent_claim_count(db: Session, user_id: int, hours: int = 48) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    return (
        db.query(func.count(Claim.id))
        .filter(Claim.user_id == user_id, Claim.created_at >= since)
        .scalar()
        or 0
    )


def _user_earning_cv(db: Session, user_id: int, days: int = 14) -> float | None:
    rows = (
        db.query(EarningDay)
        .filter(EarningDay.user_id == user_id)
        .order_by(EarningDay.earn_date.desc())
        .limit(days)
        .all()
    )
    amounts = [r.amount for r in rows]
    if len(amounts) < 5:
        return None
    m = float(mean(amounts))
    if m <= 1e-6:
        return None
    return float(pstdev(amounts) / m)


def _zone_peer_cv_median(db: Session, zone_id: str, exclude_user_id: int, cap_users: int = 50) -> float | None:
    peers = (
        db.query(User.id)
        .filter(User.zone_id == zone_id, User.id != exclude_user_id)
        .limit(cap_users)
        .all()
    )
    cvs: list[float] = []
    for (pid,) in peers:
        cv = _user_earning_cv(db, pid, 14)
        if cv is not None:
            cvs.append(cv)
    if len(cvs) < 3:
        return None
    return float(median(cvs))


def _behavioral_risk_individual_vs_zone(db: Session, user: User) -> tuple[float, dict[str, Any]]:
    """Higher when this worker's earnings swing wider than typical peers in the same zone."""
    mine = _user_earning_cv(db, user.id, 14)
    peer_med = _zone_peer_cv_median(db, user.zone_id, user.id)
    meta: dict[str, Any] = {"individual_cv": mine, "zone_peer_cv_median": peer_med}
    if mine is None:
        return 0.18, {**meta, "note": "thin_user_history"}
    if peer_med is None or peer_med <= 1e-6:
        return float(min(0.55, mine * 1.1)), {**meta, "note": "sparse_peers"}
    ratio = mine / max(peer_med, 1e-6)
    # ratio > 1 → more volatile than neighbours
    risk = float(np.clip((ratio - 1.0) * 0.85, 0.0, 0.72))
    meta["cv_ratio_vs_peers"] = round(ratio, 3)
    return risk, meta


def _weather_metrics_imply_rain(w: dict[str, Any]) -> bool:
    mm_h = float(w.get("rain_mm_hour") or 0)
    rain_24 = float(w.get("forecast_rain_24h_mm") or w.get("rain_mm_day") or 0)
    return rain_24 > 50 or mm_h > 20


def _weather_metrics_imply_heat(w: dict[str, Any]) -> bool:
    max_t = float(w.get("max_temp_next_24h") or w.get("temp_c") or 0)
    return max_t > 42.0


def _weather_integrity_risk(details: dict[str, Any] | None, force_mock: bool) -> tuple[float, dict[str, Any]]:
    if force_mock or not details:
        return 0.0, {}
    w = details.get("weather_api") if isinstance(details.get("weather_api"), dict) else details.get("weather")
    if not isinstance(w, dict):
        return 0.0, {}
    risk = 0.0
    meta: dict[str, Any] = {}
    api_rain = bool(w.get("rain_trigger"))
    api_heat = bool(w.get("heat_trigger"))
    if api_rain != _weather_metrics_imply_rain(w):
        risk += 0.36
        meta["rain_flag_metric_mismatch"] = True
    if api_heat != _weather_metrics_imply_heat(w):
        risk += 0.22
        meta["heat_flag_metric_mismatch"] = True
    return min(1.0, risk), meta


def _history_weather_risk(
    db: Session,
    user_id: int,
    current_weather: dict[str, Any],
    force_mock: bool,
) -> tuple[float, dict[str, Any]]:
    """Use rolling snapshot history to flag weak rain narratives vs stored cadence."""
    if force_mock:
        return 0.0, {}
    hist = load_weather_history(db, user_id, 16)
    if len(hist) < 5:
        return 0.0, {"history_points": len(hist)}
    risk = 0.0
    mm_hist = [float(h.get("rain_mm_h") or 0) for h in hist[-10:]]
    med_mm = float(median(mm_hist)) if mm_hist else 0.0
    cur_mm = float(current_weather.get("rain_mm_hour") or 0)
    fc24 = float(current_weather.get("forecast_rain_24h_mm") or 0)
    cur_rain_tr = bool(current_weather.get("rain_trigger"))
    if cur_rain_tr and med_mm < 2.0 and cur_mm < 6.0 and fc24 < 28.0:
        risk += 0.34
    prior_rate = sum(1 for h in hist if h.get("rain_tr")) / len(hist)
    if cur_rain_tr and prior_rate < 0.08 and fc24 < 35.0:
        risk += 0.08
    return min(0.5, risk), {"history_points": len(hist), "hist_median_rain_mm_h": round(med_mm, 3)}


def _parse_attestation(user: User) -> dict[str, Any]:
    try:
        return json.loads(user.gps_attestation_json or "{}")
    except json.JSONDecodeError:
        return {}


def _analyze_trace(samples: list[dict[str, Any]]) -> dict[str, float]:
    """Derive anti-spoofing signals from time-ordered GPS samples."""
    out: dict[str, float] = {
        "n": float(len(samples)),
        "static_score": 0.0,
        "teleport_score": 0.0,
        "accuracy_std": 0.0,
        "accuracy_mean": 0.0,
        "max_speed_kmh": 0.0,
        "duration_sec": 0.0,
    }
    if len(samples) < 2:
        return out

    accs = [float(s.get("accuracy") or 30.0) for s in samples]
    out["accuracy_mean"] = float(np.mean(accs))
    out["accuracy_std"] = float(np.std(accs)) if len(accs) > 1 else 0.0

    lats = [float(s["lat"]) for s in samples]
    lons = [float(s["lon"]) for s in samples]
    first_lat, first_lon = lats[0], lons[0]
    static_count = sum(
        1
        for la, lo in zip(lats, lons)
        if haversine_km(la, lo, first_lat, first_lon) < 0.012
    )
    out["static_score"] = min(1.0, static_count / max(len(samples), 1))

    ts0 = int(samples[0].get("ts") or 0)
    ts1 = int(samples[-1].get("ts") or 0)
    out["duration_sec"] = max(0.0, (ts1 - ts0) / 1000.0)

    max_speed = 0.0
    teleport_hits = 0
    for i in range(1, len(samples)):
        t0, t1 = int(samples[i - 1].get("ts") or 0), int(samples[i].get("ts") or 0)
        dt = max(0.001, (t1 - t0) / 1000.0)
        d_km = haversine_km(
            float(samples[i - 1]["lat"]),
            float(samples[i - 1]["lon"]),
            float(samples[i]["lat"]),
            float(samples[i]["lon"]),
        )
        v_kmh = (d_km / dt) * 3600.0
        max_speed = max(max_speed, v_kmh)
        if v_kmh > 180:
            teleport_hits += 1

    out["max_speed_kmh"] = max_speed
    out["teleport_score"] = min(1.0, teleport_hits / max(len(samples) - 1, 1))
    return out


def _swarm_coordinated_risk(db: Session, zone_id: str) -> float:
    """Aggregate / ring risk: many paid claims same zone in a short window."""
    since = datetime.now(timezone.utc) - timedelta(hours=2)
    n = (
        db.query(func.count(Claim.id))
        .join(User, Claim.user_id == User.id)
        .filter(
            User.zone_id == zone_id,
            Claim.status == "paid",
            Claim.created_at >= since,
        )
        .scalar()
    ) or 0
    if n <= 12:
        return 0.0
    return min(0.22, (n - 12) * 0.015)


def _isolation_fraud_vector(v: np.ndarray) -> float:
    raw = float(_ISO.decision_function(v.reshape(1, -1))[0])
    return float(np.clip(0.55 - raw * 1.85, 0.0, 1.0))


def evaluate_claim(
    db: Session,
    user: User,
    event_zone_id: str,
    event_id: str,
    income_drop_pct: float,
    *,
    external_details: dict[str, Any] | None = None,
    force_mock_disruption: bool = False,
) -> FraudResult:
    notes: list[str] = []
    msts: dict[str, Any] = {}

    z_radius = zone_radius_km(event_zone_id)
    ok_zone, dist_km = coords_match_claimed_zone(user.lat, user.lon, event_zone_id)
    if not ok_zone:
        notes.append(f"GPS outside claimed work zone (~{dist_km:.1f} km from hub, limit {z_radius:.1f} km)")
        msts.update({"zone_distance_km": dist_km, "zone_radius_km": z_radius, "layer": "geo_gate"})
        return FraudResult(
            score=0.96,
            notes="; ".join(notes),
            approved=False,
            msts=msts,
        )

    if duplicate_event(db, user.id, event_id):
        notes.append("Duplicate payout for same event")
        return FraudResult(score=0.93, notes="; ".join(notes), approved=False, msts={"layer": "duplicate"})

    recent_claims = _recent_claim_count(db, user.id, 48)
    velocity_risk = 0.0
    if recent_claims >= 3:
        velocity_risk = min(0.45, 0.12 + (recent_claims - 2) * 0.11)
        notes.append("High claim velocity — possible abuse pattern")

    w_integrity, w_meta = _weather_integrity_risk(external_details, force_mock_disruption)
    if w_meta.get("rain_flag_metric_mismatch") or w_meta.get("heat_flag_metric_mismatch"):
        notes.append("Weather API flags disagree with raw metrics — review")

    w_api = {}
    if isinstance(external_details, dict):
        w_api = external_details.get("weather_api") or external_details.get("weather") or {}
    if not isinstance(w_api, dict):
        w_api = {}

    hist_risk, hist_meta = _history_weather_risk(db, user.id, w_api, force_mock_disruption)
    if hist_risk >= 0.25:
        notes.append("Rain narrative weak vs recent environmental history")

    beh_risk, beh_meta = _behavioral_risk_individual_vs_zone(db, user)
    if beh_risk >= 0.35:
        notes.append("Individual earning volatility vs zone peers — elevated review")

    att = _parse_attestation(user)
    samples = att.get("samples") if isinstance(att.get("samples"), list) else []
    trace = _analyze_trace(samples) if samples else {}

    stale_penalty = 0.0
    captured_iso = att.get("captured_at")
    if isinstance(captured_iso, str):
        try:
            cap = datetime.fromisoformat(captured_iso.replace("Z", "+00:00"))
            if cap.tzinfo is None:
                cap = cap.replace(tzinfo=timezone.utc)
            age_h = (datetime.now(timezone.utc) - cap).total_seconds() / 3600.0
            if age_h > 72:
                stale_penalty = min(0.18, (age_h - 72) / 500.0)
                notes.append("GPS attestation stale — elevated review")
        except ValueError:
            stale_penalty = 0.08

    no_live_trace = len(samples) < 3
    if no_live_trace:
        stale_penalty += 0.12
        notes.append("No recent multi-point GPS trace — MSTS partially blind")

    static_score = float(trace.get("static_score", 0.0))
    teleport_score = float(trace.get("teleport_score", 0.0))
    max_speed = float(trace.get("max_speed_kmh", 0.0))
    acc_std = float(trace.get("accuracy_std", 0.0))
    acc_mean = float(trace.get("accuracy_mean", 25.0))

    noise_anomaly = 0.0
    if len(samples) >= 4 and acc_std < 1.5 and acc_mean < 8.0:
        noise_anomaly = 0.22
        notes.append("GPS accuracy unnaturally stable — possible spoof")

    if max_speed > 240:
        notes.append("Impossible movement speed between fixes — blocked")
        return FraudResult(
            score=0.94,
            notes="; ".join(notes),
            approved=False,
            msts={**trace, "max_speed_kmh": max_speed, "layer": "teleport"},
        )

    if static_score > 0.92 and len(samples) >= 8:
        notes.append("Movement trace static — spoof pattern risk")
        static_score = min(1.0, static_score + 0.05)

    dist_norm = min(1.0, dist_km / max(z_radius, 1.0))
    acc_noise_norm = min(1.0, acc_std / 45.0) if acc_std > 0 else 0.35
    swarm = _swarm_coordinated_risk(db, user.zone_id)

    delivery_context_risk = float(
        np.clip((w_integrity + hist_risk + velocity_risk + 0.55 * beh_risk) / 2.15, 0.0, 1.0)
    )

    feat = np.array(
        [
            dist_norm,
            min(1.0, static_score + noise_anomaly * 0.5),
            min(1.0, teleport_score + (0.15 if max_speed > 120 else 0.0)),
            acc_noise_norm,
            income_drop_pct,
            swarm,
            min(1.0, stale_penalty * 3.5),
            0.35 if no_live_trace else 0.08,
            min(1.0, beh_risk + 0.15 * velocity_risk),
            min(1.0, w_integrity + hist_risk + 0.4 * velocity_risk),
        ],
        dtype=np.float64,
    )

    if_score = _isolation_fraud_vector(feat)
    rule_score = (
        0.16 * static_score
        + 0.24 * teleport_score
        + 0.10 * swarm
        + 0.13 * stale_penalty
        + 0.10 * noise_anomaly
        + (0.12 if no_live_trace else 0.0)
        + 0.18 * velocity_risk
        + 0.14 * w_integrity
        + 0.12 * hist_risk
        + 0.16 * beh_risk
    )
    if income_drop_pct < 0.4:
        rule_score += 0.12
        notes.append("Income drop below threshold (possible inactivity)")

    combined = 0.52 * if_score + 0.48 * min(1.0, rule_score)
    if income_drop_pct > 0.88:
        combined += 0.08
        notes.append("Extreme drop — elevated review")

    combined = float(min(0.99, max(0.08, combined)))
    approved = combined < 0.75

    if income_drop_pct >= 0.4:
        notes.append("Income drop consistent with disruption")

    msts = {
        "zone_distance_km": dist_km,
        "zone_radius_km": z_radius,
        "isolation_forest_risk": round(if_score, 4),
        "rule_risk": round(rule_score, 4),
        "swarm_risk": round(swarm, 4),
        "static_score": round(static_score, 4),
        "teleport_score": round(teleport_score, 4),
        "accuracy_std_m": round(acc_std, 3),
        "samples": int(len(samples)),
        "stale_penalty": round(stale_penalty, 4),
        "weather_integrity_risk": round(w_integrity, 4),
        "weather_history_risk": round(hist_risk, 4),
        "claim_velocity_48h": recent_claims,
        "behavioral_risk": round(beh_risk, 4),
        "delivery_context_risk": round(delivery_context_risk, 4),
        "individual_cv": beh_meta.get("individual_cv"),
        "zone_peer_cv_median": beh_meta.get("zone_peer_cv_median"),
        "cv_ratio_vs_peers": beh_meta.get("cv_ratio_vs_peers"),
        "behavior_note": beh_meta.get("note"),
        **hist_meta,
    }

    return FraudResult(
        score=combined,
        notes="; ".join(n for n in notes if n),
        approved=approved,
        msts=msts,
    )
