"""Work zone centers — keep `id` / coords aligned with frontend `src/data/zones.ts`."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class ZoneCenter(TypedDict):
    id: str
    lat: float
    lon: float
    # Sub-city / neighbourhood hubs use a tighter radius (Phase 3 granularity).
    radius_km: NotRequired[float]


# Default when `radius_km` is omitted — metro-scale hubs.
DEFAULT_ZONE_RADIUS_KM = 32.0

WORK_ZONE_CENTERS: list[ZoneCenter] = [
    # --- Metro-scale (legacy) ---
    {"id": "chennai-t-nagar", "lat": 13.0418, "lon": 80.2341},
    {"id": "chennai-velachery", "lat": 12.9815, "lon": 80.2209},
    {"id": "chennai-omr", "lat": 12.9499, "lon": 80.2381},
    {"id": "bengaluru-koramangala", "lat": 12.9352, "lon": 77.6245},
    {"id": "bengaluru-whitefield", "lat": 12.9698, "lon": 77.75},
    {"id": "bengaluru-indiranagar", "lat": 12.9719, "lon": 77.6412},
    {"id": "bengaluru-electronic-city", "lat": 12.8456, "lon": 77.6603},
    {"id": "mumbai-andheri", "lat": 19.1136, "lon": 72.8697},
    {"id": "mumbai-borivali", "lat": 19.2313, "lon": 72.8564},
    {"id": "mumbai-thane", "lat": 19.2183, "lon": 72.9781},
    {"id": "delhi-connaught", "lat": 28.6315, "lon": 77.2167},
    {"id": "delhi-rohini", "lat": 28.7495, "lon": 77.0627},
    {"id": "gurugram-cyber-city", "lat": 28.495, "lon": 77.089},
    {"id": "noida-sector-18", "lat": 28.5703, "lon": 77.3216},
    {"id": "hyderabad-hitec", "lat": 17.4474, "lon": 78.3762},
    {"id": "hyderabad-gachibowli", "lat": 17.4401, "lon": 78.3489},
    {"id": "pune-kothrud", "lat": 18.5074, "lon": 73.8077},
    {"id": "pune-viman-nagar", "lat": 18.5679, "lon": 73.9143},
    {"id": "kolkata-park-street", "lat": 22.5511, "lon": 88.3527},
    {"id": "ahmedabad-satellite", "lat": 23.0258, "lon": 72.5873},
    {"id": "jaipur-vaishali", "lat": 26.9124, "lon": 75.7873},
    {"id": "kochi-edappally", "lat": 10.0262, "lon": 76.3084},
    {"id": "coimbatore-rs-puram", "lat": 11.0168, "lon": 76.9558},
    {"id": "lucknow-gomti", "lat": 26.8467, "lon": 80.9462},
    {"id": "indore-vijay-nagar", "lat": 22.7533, "lon": 75.8937},
    {"id": "chandigarh", "lat": 30.7333, "lon": 76.7794},
    {"id": "visakhapatnam-mvp", "lat": 17.7215, "lon": 83.318},
    {"id": "bhubaneswar-patia", "lat": 20.356, "lon": 85.8246},
    # --- Sub-city / neighbourhood (tighter radius) ---
    {"id": "chennai-anna-nagar", "lat": 13.0846, "lon": 80.2105, "radius_km": 11.0},
    {"id": "chennai-adyar", "lat": 13.0067, "lon": 80.2206, "radius_km": 10.5},
    {"id": "chennai-porur", "lat": 13.0382, "lon": 80.1566, "radius_km": 10.0},
    {"id": "chennai-tambaram", "lat": 12.9249, "lon": 80.1, "radius_km": 11.0},
    {"id": "bengaluru-hsr-layout", "lat": 12.9116, "lon": 77.6389, "radius_km": 9.5},
    {"id": "bengaluru-marathahalli", "lat": 12.9591, "lon": 77.6974, "radius_km": 10.0},
    {"id": "bengaluru-yelahanka", "lat": 13.1007, "lon": 77.5963, "radius_km": 12.0},
    {"id": "bengaluru-mg-road", "lat": 12.9753, "lon": 77.6067, "radius_km": 8.0},
    {"id": "mumbai-bandra", "lat": 19.0544, "lon": 72.8406, "radius_km": 9.0},
    {"id": "mumbai-powai", "lat": 19.1176, "lon": 72.9091, "radius_km": 10.0},
    {"id": "mumbai-navi-vashi", "lat": 19.0807, "lon": 73.0103, "radius_km": 11.0},
    {"id": "delhi-dwarka", "lat": 28.5921, "lon": 77.046, "radius_km": 12.0},
    {"id": "delhi-saket", "lat": 28.5244, "lon": 77.2065, "radius_km": 10.0},
    {"id": "hyderabad-madhapur", "lat": 17.4483, "lon": 78.3915, "radius_km": 9.0},
    {"id": "hyderabad-secunderabad", "lat": 17.4399, "lon": 78.4983, "radius_km": 11.0},
    {"id": "pune-hinjewadi", "lat": 18.5912, "lon": 73.7389, "radius_km": 12.0},
    {"id": "kolkata-salt-lake", "lat": 22.5867, "lon": 88.4172, "radius_km": 10.5},
]

ZONE_BY_ID: dict[str, ZoneCenter] = {z["id"]: z for z in WORK_ZONE_CENTERS}

# Back-compat alias — default radius for docs / health checks.
ZONE_MATCH_RADIUS_KM = DEFAULT_ZONE_RADIUS_KM


def zone_radius_km(zone_id: str) -> float:
    z = ZONE_BY_ID.get(zone_id)
    if not z:
        return DEFAULT_ZONE_RADIUS_KM
    r = z.get("radius_km")
    return float(r) if r is not None else DEFAULT_ZONE_RADIUS_KM
