import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Optional
import requests
from config import (
    GRID_CELL_SIZE_DEG, GRID_CELL_RADIUS_KM, CELL_CACHE_TTL_MINUTES,
    HOURLY_RAIN_SEV2, HOURLY_RAIN_SEV3, HOURLY_RAIN_SEV4,
    ROLLING_3H_RAIN_SEV3, ROLLING_3H_RAIN_SEV4,
    WIND_GUST_SEV2, WIND_GUST_SEV3, WIND_GUST_SEV4,
    HEAT_SEV2, HEAT_SEV3, WMO_THUNDERSTORM_SEV2, WMO_THUNDERSTORM_SEV3
)
from models import WeatherCellCache, HazardZone

logger = logging.getLogger(__name__)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"

def snap_to_grid(lat: float, lon: float, grid_size: float = GRID_CELL_SIZE_DEG) -> Tuple[float, float, str]:
    """
    Snaps GPS coordinates to cell center.
    Only rounded cell-center coordinates are ever sent to Open-Meteo (Privacy requirement).
    Returns (cell_center_lat, cell_center_lon, cell_id).
    """
    cell_lat = round(round(lat / grid_size) * grid_size, 4)
    cell_lon = round(round(lon / grid_size) * grid_size, 4)
    cell_id = f"{cell_lat:.2f}_{cell_lon:.2f}"
    return cell_lat, cell_lon, cell_id

def get_neighborhood_cells(lat: float, lon: float, grid_size: float = GRID_CELL_SIZE_DEG) -> List[Tuple[float, float, str]]:
    """Returns the 3x3 block of cells around a point (9 cells total) to catch approaching storms."""
    center_lat, center_lon, _ = snap_to_grid(lat, lon, grid_size)
    cells = []
    offsets = [-1, 0, 1]
    for d_lat in offsets:
        for d_lon in offsets:
            n_lat = round(center_lat + d_lat * grid_size, 4)
            n_lon = round(center_lon + d_lon * grid_size, 4)
            n_id = f"{n_lat:.2f}_{n_lon:.2f}"
            cells.append((n_lat, n_lon, n_id))
    return cells

def fetch_open_meteo_batch(cells: List[Tuple[float, float, str]]) -> Dict[str, Dict[str, Any]]:
    """
    Batches multi-location request to Open-Meteo using comma-separated coordinates.
    Returns mapping of cell_id -> forecast_data.
    """
    if not cells:
        return {}

    lats_str = ",".join(str(c[0]) for c in cells)
    lons_str = ",".join(str(c[1]) for c in cells)

    params = {
        "latitude": lats_str,
        "longitude": lons_str,
        "hourly": "precipitation,rain,wind_gusts_10m,weather_code,temperature_2m",
        "current_weather": "true",
        "timezone": "UTC",
        "forecast_days": 2,
    }

    try:
        resp = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=12)
        resp.raise_for_status()
        raw_res = resp.json()
    except Exception as e:
        logger.error(f"Error querying Open-Meteo forecast: {e}")
        return {}

    results = {}
    if isinstance(raw_res, list):
        for idx, item in enumerate(raw_res):
            if idx < len(cells):
                cell_id = cells[idx][2]
                results[cell_id] = item
    elif isinstance(raw_res, dict):
        if len(cells) == 1:
            results[cells[0][2]] = raw_res
    return results

def parse_cell_hazards(cell_lat: float, cell_lon: float, cell_id: str, forecast_data: Dict[str, Any], now_utc: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """
    ACTIVE-ONLY RULE:
    Builds hazard zones only from HOURLY data from the CURRENT HOUR onward.
    Past hours (earlier today) must NEVER create a hazard zone.
    Merges hourly breaches into time-aware HazardZones.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    hourly = forecast_data.get("hourly", {})
    times = hourly.get("time", [])
    precip = hourly.get("precipitation", [])
    winds = hourly.get("wind_gusts_10m", [])
    temps = hourly.get("temperature_2m", [])
    wmo_codes = hourly.get("weather_code", [])

    if not times:
        return []

    # Current hour baseline in UTC (e.g. 2026-10-10T02:00:00)
    current_hour_iso = now_utc.strftime("%Y-%m-%dT%H:00")

    breaches_by_type: Dict[str, List[Dict[str, Any]]] = {
        "HEAVY_RAIN": [],
        "HIGH_WIND": [],
        "THUNDERSTORM": [],
        "HEAT": []
    }

    for i, t_str in enumerate(times):
        # Ignore past hours strictly!
        if t_str < current_hour_iso:
            continue
        
        # Consider up to 24 hours into the future
        try:
            hour_dt = datetime.fromisoformat(t_str).replace(tzinfo=timezone.utc)
            if (hour_dt - now_utc).total_seconds() > 24 * 3600:
                continue
        except Exception:
            continue

        p_val = precip[i] if i < len(precip) and precip[i] is not None else 0.0
        w_val = winds[i] if i < len(winds) and winds[i] is not None else 0.0
        temp_val = temps[i] if i < len(temps) and temps[i] is not None else 0.0
        code_val = wmo_codes[i] if i < len(wmo_codes) and wmo_codes[i] is not None else 0

        # Check Hourly Rain
        rain_sev = 0
        if p_val >= HOURLY_RAIN_SEV4:
            rain_sev = 4
        elif p_val >= HOURLY_RAIN_SEV3:
            rain_sev = 3
        elif p_val >= HOURLY_RAIN_SEV2:
            rain_sev = 2
        
        # Check rolling 3-hour precipitation
        if i >= 2 and i < len(precip):
            r3_val = sum((precip[k] or 0.0) for k in range(i-2, i+1))
            if r3_val >= ROLLING_3H_RAIN_SEV4:
                rain_sev = max(rain_sev, 4)
            elif r3_val >= ROLLING_3H_RAIN_SEV3:
                rain_sev = max(rain_sev, 3)

        if rain_sev >= 2:
            breaches_by_type["HEAVY_RAIN"].append({"dt": hour_dt, "severity": rain_sev, "val": p_val})

        # Wind gusts
        wind_sev = 0
        if w_val >= WIND_GUST_SEV4:
            wind_sev = 4
        elif w_val >= WIND_GUST_SEV3:
            wind_sev = 3
        elif w_val >= WIND_GUST_SEV2:
            wind_sev = 2

        if wind_sev >= 2:
            breaches_by_type["HIGH_WIND"].append({"dt": hour_dt, "severity": wind_sev, "val": w_val})

        # Thunderstorm WMO codes
        if code_val in WMO_THUNDERSTORM_SEV3:
            breaches_by_type["THUNDERSTORM"].append({"dt": hour_dt, "severity": 3, "val": code_val})
        elif code_val in WMO_THUNDERSTORM_SEV2:
            breaches_by_type["THUNDERSTORM"].append({"dt": hour_dt, "severity": 2, "val": code_val})

        # Extreme Heat
        heat_sev = 0
        if temp_val >= HEAT_SEV3:
            heat_sev = 3
        elif temp_val >= HEAT_SEV2:
            heat_sev = 2

        if heat_sev >= 2:
            breaches_by_type["HEAT"].append({"dt": hour_dt, "severity": heat_sev, "val": temp_val})

    # Consolidate consecutive or clustered breaches into single HazardZones
    created_zones = []
    source_badge_time = now_utc.strftime("%H:%M")

    for h_type, items in breaches_by_type.items():
        if not items:
            continue
        max_sev = max(item["severity"] for item in items)
        first_time = min(item["dt"] for item in items)
        last_time = max(item["dt"] for item in items) + timedelta(hours=1)

        zone_id = f"om_{cell_id}_{h_type.lower()}"
        message_key = f"{h_type.lower()}_hourly"
        
        zone_dict = {
            "id": zone_id,
            "type": h_type,
            "severity": max_sev,
            "center_lat": cell_lat,
            "center_lon": cell_lon,
            "radius_km": GRID_CELL_RADIUS_KM,
            "start_time": first_time,
            "end_time": last_time,
            "source": f"Open-Meteo forecast, updated {source_badge_time}",
            "source_url": "https://open-meteo.com",
            "message_key": message_key,
            "message_params": json.dumps({
                "cell_id": cell_id,
                "first_hour": first_time.strftime("%H:%M"),
                "end_hour": last_time.strftime("%H:%M"),
                "severity": max_sev
            }),
            "created_at": now_utc,
            "verified": False,  # Model forecast badge
            "cell_id": cell_id
        }
        created_zones.append(zone_dict)

    return created_zones
