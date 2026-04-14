"""OpenWeatherMap (current + 24h forecast) + WAQI — real APIs; mocks only if ALLOW_MOCKS=true."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.services.errors import IntegrationError


@dataclass
class WeatherSnapshot:
    rain_mm_day: float
    rain_mm_hour: float
    temp_c: float
    heat_trigger: bool
    rain_trigger: bool
    source: str
    forecast_rain_24h_mm: float
    max_temp_next_24h: float


@dataclass
class AQISnapshot:
    aqi_us: float
    severe_pollution: bool
    source: str


def _mock_weather() -> WeatherSnapshot:
    return WeatherSnapshot(
        rain_mm_day=12.0,
        rain_mm_hour=2.0,
        temp_c=36.0,
        heat_trigger=False,
        rain_trigger=False,
        source="mock",
        forecast_rain_24h_mm=10.0,
        max_temp_next_24h=35.0,
    )


def _mock_aqi() -> AQISnapshot:
    return AQISnapshot(aqi_us=80.0, severe_pollution=False, source="mock")


async def fetch_openweather(lat: float, lon: float) -> WeatherSnapshot:
    key = settings.openweather_api_key
    if not key:
        if settings.allow_mocks:
            return _mock_weather()
        raise IntegrationError(
            "Set OPENWEATHER_API_KEY in .env for live weather (or ALLOW_MOCKS=true for dev).",
            "openweather",
        )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r_cur = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"lat": lat, "lon": lon, "appid": key, "units": "metric"},
            )
            r_cur.raise_for_status()
            cur = r_cur.json()

            r_fc = await client.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={"lat": lat, "lon": lon, "appid": key, "units": "metric"},
            )
            r_fc.raise_for_status()
            fc = r_fc.json()
    except httpx.HTTPStatusError as e:
        raise IntegrationError(
            f"OpenWeather HTTP {e.response.status_code} — invalid key, billing, or API not enabled for this key.",
            "openweather",
        ) from e
    except httpx.RequestError as e:
        raise IntegrationError(f"OpenWeather network error: {e}", "openweather") from e

    rain_cur = cur.get("rain") or {}
    mm_h = float(rain_cur.get("1h", 0) or 0)
    if mm_h == 0 and rain_cur.get("3h"):
        mm_h = float(rain_cur["3h"]) / 3.0

    temp_now = float(cur["main"]["temp"])

    # Next 24h = first 8 slots × 3h
    slots = fc.get("list", [])[:8]
    rain_24 = 0.0
    max_t_24 = temp_now
    temps_above_40 = 0
    max_3h_rain = 0.0
    for it in slots:
        main = it.get("main") or {}
        max_t_24 = max(max_t_24, float(main.get("temp_max", main.get("temp", 0))))
        tavg = float(main.get("temp", temp_now))
        if tavg > 40:
            temps_above_40 += 1
        rn = it.get("rain") or {}
        h3 = float(rn.get("3h", 0) or 0)
        rain_24 += h3
        max_3h_rain = max(max_3h_rain, h3)

    # README: heavy rain >50mm/day OR >20mm/hr (use max 3h rate as mm/h proxy)
    mm_h_rate = max(mm_h, max_3h_rain / 3.0 if max_3h_rain else 0.0)
    rain_tr = rain_24 > 50 or mm_h_rate > 20
    # README: extreme heat >40°C sustained 3+ hours → ≥2 consecutive 3h slots above 40°C (6h)
    heat_tr = temps_above_40 >= 2 or max_t_24 > 42

    return WeatherSnapshot(
        rain_mm_day=max(rain_24, mm_h * 8.0),
        rain_mm_hour=mm_h_rate,
        temp_c=temp_now,
        heat_trigger=heat_tr,
        rain_trigger=rain_tr,
        source="openweathermap",
        forecast_rain_24h_mm=round(rain_24, 2),
        max_temp_next_24h=round(max_t_24, 2),
    )


async def fetch_waqi(lat: float, lon: float) -> AQISnapshot:
    token = settings.waqi_api_token
    if not token:
        if settings.allow_mocks:
            return _mock_aqi()
        raise IntegrationError(
            "Set WAQI_API_TOKEN in .env for live AQI (or ALLOW_MOCKS=true for dev).",
            "waqi",
        )

    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url, params={"token": token})
            r.raise_for_status()
            j = r.json()
    except Exception as e:
        raise IntegrationError(f"WAQI HTTP error: {e}", "waqi") from e

    if j.get("status") != "ok":
        # Very common: no monitoring station near this GPS — do not fail whole /monitoring/live
        return AQISnapshot(
            aqi_us=0.0,
            severe_pollution=False,
            source="waqi_no_station",
        )

    data = j.get("data")
    if not isinstance(data, dict):
        return AQISnapshot(0.0, False, "waqi_bad_payload")

    raw_aq = data.get("aqi")
    if raw_aq in (None, "-", ""):
        return AQISnapshot(0.0, False, "waqi_no_reading")
    try:
        aqi = float(raw_aq)
    except (TypeError, ValueError):
        return AQISnapshot(0.0, False, "waqi_unparseable")

    return AQISnapshot(aqi_us=aqi, severe_pollution=aqi > 300, source="waqi")


async def fetch_openweather_air_pollution(lat: float, lon: float) -> AQISnapshot | None:
    """
    Free tier: same OPENWEATHER_API_KEY as weather.
    https://openweathermap.org/api/air-pollution
    Used when WAQI has no station nearby.
    """
    key = settings.openweather_api_key
    if not key:
        return None
    url = "https://api.openweathermap.org/data/2.5/air_pollution"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, params={"lat": lat, "lon": lon, "appid": key})
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None
    lst = data.get("list") or []
    if not lst:
        return None
    item = lst[0]
    main = item.get("main") or {}
    comp = item.get("components") or {}
    # OWM index 1=good … 5=very poor — map to rough US AQI scale for UI
    owm_idx = int(main.get("aqi", 1))
    approx_us = {1: 45.0, 2: 95.0, 3: 145.0, 4: 205.0, 5: 320.0}.get(owm_idx, 100.0)
    pm25 = float(comp.get("pm2_5") or 0)
    # Align severe air trigger with README (AQI > 300) using PM2.5 / index
    severe = approx_us > 300 or owm_idx >= 5 or pm25 > 125.4
    return AQISnapshot(
        aqi_us=approx_us,
        severe_pollution=severe,
        source="openweather_air_pollution",
    )


async def fetch_all_triggers(lat: float, lon: float) -> dict[str, Any]:
    w = await fetch_openweather(lat, lon)
    a = await fetch_waqi(lat, lon)
    # Free fallback when no WAQI station (same OpenWeather key)
    if (
        a.source in ("waqi_no_station", "waqi_no_reading", "waqi_bad_payload", "waqi_unparseable")
        or (a.aqi_us == 0.0 and not a.severe_pollution)
    ):
        ow_air = await fetch_openweather_air_pollution(lat, lon)
        if ow_air is not None:
            a = ow_air
    return {
        "weather": {
            "rain_mm_day": w.rain_mm_day,
            "rain_mm_hour": w.rain_mm_hour,
            "temp_c": w.temp_c,
            "forecast_rain_24h_mm": w.forecast_rain_24h_mm,
            "max_temp_next_24h": w.max_temp_next_24h,
            "rain_trigger": w.rain_trigger,
            "heat_trigger": w.heat_trigger,
            "source": w.source,
        },
        "aqi": {
            "aqi_us": a.aqi_us,
            "severe_pollution": a.severe_pollution,
            "source": a.source,
            "pm2_5_estimated": a.source == "openweather_air_pollution",
        },
    }


def _mock_parametric_week_outlook() -> dict[str, Any]:
    """Demo week when APIs are off — still returns the full insurer shape."""
    days = []
    for i in range(7):
        days.append(
            {
                "date": f"2026-04-{13 + i:02d}",
                "rain_mm_est": 8.0 + (i % 3) * 6.0,
                "max_temp_c": 34.0 + (i % 4),
                "disruption_pressure_0_1": round(0.25 + (i % 5) * 0.1, 2),
                "drivers": ["demo_forecast_slot"],
            }
        )
    return {
        "source": "mock",
        "anchor": {"lat": 13.08, "lon": 80.27},
        "days": days,
        "summary": {
            "forecast_horizon_days": len(days),
            "elevated_disruption_days": 3,
            "mean_disruption_pressure": 0.42,
            "peak_pressure_date": days[2]["date"],
            "claim_environment": "elevated_vs_typical",
            "insurer_narrative": (
                "Demo week: several days show elevated rain/heat stress vs baseline — "
                "expect higher parametric trigger evaluations in outdoor gig zones."
            ),
        },
    }


async def parametric_week_outlook(lat: float, lon: float) -> dict[str, Any]:
    """
    Bucket OpenWeather 3-hour forecast into calendar days (~5–7 days of slots).
    Surfaces an insurer-facing 'next week' style disruption / claim-pressure view.
    """
    key = settings.openweather_api_key
    if not key:
        if settings.allow_mocks:
            return _mock_parametric_week_outlook()
        raise IntegrationError(
            "Set OPENWEATHER_API_KEY for week outlook (or ALLOW_MOCKS=true).",
            "openweather",
        )

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            r_fc = await client.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={"lat": lat, "lon": lon, "appid": key, "units": "metric"},
            )
            r_fc.raise_for_status()
            fc = r_fc.json()
    except httpx.HTTPStatusError as e:
        raise IntegrationError(
            f"OpenWeather forecast HTTP {e.response.status_code}",
            "openweather",
        ) from e
    except httpx.RequestError as e:
        raise IntegrationError(f"OpenWeather forecast network error: {e}", "openweather") from e

    slots = fc.get("list") or []
    by_day: dict[str, list[dict[str, float]]] = defaultdict(list)
    for it in slots:
        dt_u = it.get("dt")
        if not dt_u:
            continue
        day = datetime.fromtimestamp(int(dt_u), tz=timezone.utc).date().isoformat()
        main = it.get("main") or {}
        rn = it.get("rain") or {}
        h3 = float(rn.get("3h", 0) or 0)
        tmx = float(main.get("temp_max", main.get("temp", 0)))
        tmn = float(main.get("temp_min", main.get("temp", 0)))
        by_day[day].append({"rain_3h": h3, "temp_max": tmx, "temp_min": tmn})

    days_out: list[dict[str, Any]] = []
    for day in sorted(by_day.keys()):
        chunks = by_day[day]
        total_rain = sum(c["rain_3h"] for c in chunks)
        max_t = max((c["temp_max"] for c in chunks), default=0.0)
        min_t = min((c["temp_min"] for c in chunks), default=0.0)
        # Align with README-style triggers: heavy rain band, heat stress band.
        rain_p = min(1.0, total_rain / 75.0) if total_rain > 0 else 0.0
        heat_p = min(1.0, max(0.0, max_t - 36.0) / 10.0)
        slot_rain_peak = max((c["rain_3h"] for c in chunks), default=0.0)
        burst_p = min(1.0, (slot_rain_peak / 3.0) / 25.0)  # proxy for >20mm/h style bursts
        pressure = float(min(1.0, max(rain_p, heat_p * 0.92, burst_p * 0.85)))
        drivers: list[str] = []
        if total_rain >= 35:
            drivers.append("elevated_daily_rain_total")
        if max_t >= 40:
            drivers.append("heat_stress_peak")
        if slot_rain_peak >= 15:
            drivers.append("heavy_short_interval_rain")
        if not drivers:
            drivers.append("within_typical_band")

        days_out.append(
            {
                "date": day,
                "rain_mm_est": round(total_rain, 1),
                "max_temp_c": round(max_t, 1),
                "min_temp_c": round(min_t, 1),
                "disruption_pressure_0_1": round(pressure, 3),
                "drivers": drivers,
            }
        )

    if not days_out:
        return {
            "source": "openweathermap",
            "anchor": {"lat": lat, "lon": lon},
            "days": [],
            "summary": {
                "forecast_horizon_days": 0,
                "insurer_narrative": "No forecast slots returned — try again later.",
            },
        }

    pressures = [d["disruption_pressure_0_1"] for d in days_out]
    mean_p = sum(pressures) / len(pressures)
    elevated = sum(1 for p in pressures if p >= 0.42)
    peak_day = max(days_out, key=lambda d: d["disruption_pressure_0_1"])

    if mean_p >= 0.38:
        env = "elevated_vs_typical"
        nar = (
            f"Next {len(days_out)} day(s): mean disruption pressure {mean_p:.2f} — "
            "expect above-average parametric evaluations in covered zones."
        )
    elif mean_p <= 0.22:
        env = "below_typical"
        nar = (
            f"Next {len(days_out)} day(s): calmer environmental band — "
            "likely fewer weather-driven triggers unless RSS/social signals spike."
        )
    else:
        env = "typical"
        nar = (
            f"Next {len(days_out)} day(s): mixed conditions — monitor peak day {peak_day['date']} "
            f"(pressure {peak_day['disruption_pressure_0_1']:.2f})."
        )

    return {
        "source": "openweathermap",
        "anchor": {"lat": lat, "lon": lon},
        "days": days_out,
        "summary": {
            "forecast_horizon_days": len(days_out),
            "elevated_disruption_days": elevated,
            "mean_disruption_pressure": round(mean_p, 3),
            "peak_pressure_date": peak_day["date"],
            "peak_pressure_value": peak_day["disruption_pressure_0_1"],
            "claim_environment": env,
            "insurer_narrative": nar,
        },
    }
