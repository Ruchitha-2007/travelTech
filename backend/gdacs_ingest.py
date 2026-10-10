import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import requests
from config import GDACS_RADIUS_CONFIG
from safety_engine import classify_zone_state

logger = logging.getLogger(__name__)

GDACS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"

def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        # Handles formats like 2026-10-09T20:25:40 or with Z/+00:00
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        logger.warning(f"Failed to parse datetime '{dt_str}': {e}")
        return None

def extract_centroid(geometry: Dict[str, Any]) -> Optional[tuple[float, float]]:
    """Extracts (lat, lon) from GeoJSON Point or calculates centroid for LineString/Polygon."""
    if not geometry:
        return None
    geo_type = geometry.get("type", "")
    coords = geometry.get("coordinates", [])
    if not coords:
        return None

    if geo_type == "Point" and len(coords) >= 2:
        return float(coords[1]), float(coords[0])  # lat, lon
    elif geo_type == "Polygon" and len(coords) > 0 and len(coords[0]) > 0:
        ring = coords[0]
        lats = [pt[1] for pt in ring if len(pt) >= 2]
        lons = [pt[0] for pt in ring if len(pt) >= 2]
        if lats and lons:
            return sum(lats) / len(lats), sum(lons) / len(lons)
    elif geo_type == "MultiPolygon" and len(coords) > 0:
        all_lats, all_lons = [], []
        for poly in coords:
            if poly and len(poly) > 0:
                for pt in poly[0]:
                    if len(pt) >= 2:
                        all_lats.append(pt[1])
                        all_lons.append(pt[0])
        if all_lats and all_lons:
            return sum(all_lats) / len(all_lats), sum(all_lons) / len(all_lons)
    elif geo_type == "LineString":
        lats = [pt[1] for pt in coords if len(pt) >= 2]
        lons = [pt[0] for pt in coords if len(pt) >= 2]
        if lats and lons:
            return sum(lats) / len(lats), sum(lons) / len(lons)

    return None

def map_gdacs_type(event_type: str) -> str:
    mapping = {
        "TC": "CYCLONE",
        "FL": "FLOOD",
        "EQ": "EARTHQUAKE",
        "TS": "TSUNAMI",
        "DR": "HEAT",
        "WF": "MANUAL",
        "VO": "MANUAL",
    }
    return mapping.get(event_type, "MANUAL")

def map_gdacs_severity(alert_level: str) -> int:
    lvl = (alert_level or "").strip().lower()
    if lvl == "red":
        return 4
    elif lvl == "orange":
        return 3
    elif lvl == "green":
        return 1
    return 2

def get_gdacs_radius(event_type: str, alert_level: str) -> float:
    lvl = (alert_level or "").capitalize()
    type_cfg = GDACS_RADIUS_CONFIG.get(event_type, GDACS_RADIUS_CONFIG["DEFAULT"])
    return type_cfg.get(lvl, type_cfg.get("Orange", 50.0))

def fetch_and_parse_gdacs(now_utc: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """
    Fetches GDACS events and converts active or upcoming events into circular HazardZones.
    Filters out expired events strictly in accordance with ACTIVE-ONLY RULE.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    try:
        resp = requests.get(GDACS_URL, timeout=12)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Error fetching GDACS events: {e}")
        return []

    features = data.get("features", [])
    valid_zones = []

    for feat in features:
        props = feat.get("properties", {})
        geometry = feat.get("geometry", {})
        
        # ACTIVE-ONLY RULE checks
        is_current = str(props.get("iscurrent", "true")).lower()
        if is_current == "false":
            continue

        from_date = parse_iso_datetime(props.get("fromdate"))
        to_date = parse_iso_datetime(props.get("todate"))

        # Skip if dates missing or unparseable
        if not to_date:
            logger.info(f"Skipping GDACS event {props.get('eventid')} due to missing todate.")
            continue
        if not from_date:
            from_date = to_date - timedelta(hours=6)

        # In GDACS GeoJSON API, todate is the observation/bulletin timestamp.
        # If iscurrent is true and published recently, the disaster event is currently ongoing.
        effective_end_time = to_date
        if is_current == "true" and to_date >= (now_utc - timedelta(hours=48)):
            effective_end_time = max(to_date + timedelta(hours=24), now_utc + timedelta(hours=12))

        # Check zone state (must be ACTIVE or UPCOMING)
        state = classify_zone_state(from_date, effective_end_time, now_utc)
        if state not in ("ACTIVE", "UPCOMING"):
            # Expired or far future (> 24h away)
            continue

        centroid = extract_centroid(geometry)
        if not centroid:
            continue
        lat, lon = centroid

        raw_type = props.get("eventtype", "DEFAULT")
        hz_type = map_gdacs_type(raw_type)
        alert_level = props.get("alertlevel", "Orange")
        severity = map_gdacs_severity(alert_level)
        radius = get_gdacs_radius(raw_type, alert_level)

        event_name = props.get("name") or props.get("eventname") or f"{hz_type} Event"
        details_url = ""
        url_obj = props.get("url")
        if isinstance(url_obj, dict):
            details_url = url_obj.get("details", "")
        elif isinstance(url_obj, str):
            details_url = url_obj

        zone_data = {
            "id": f"gdacs_{props.get('eventtype', 'ev')}_{props.get('eventid', '')}_{props.get('episodeid', '')}",
            "type": hz_type,
            "severity": severity,
            "center_lat": round(lat, 4),
            "center_lon": round(lon, 4),
            "radius_km": radius,
            "start_time": from_date,
            "end_time": effective_end_time,
            "source": "GDACS",
            "source_url": details_url or "https://www.gdacs.org",
            "message_key": f"{hz_type.lower()}_warning",
            "message_params": json.dumps({"name": event_name, "alert_level": alert_level}),
            "created_at": now_utc,
            "verified": True,
            "cell_id": None
        }
        valid_zones.append(zone_data)

    return valid_zones
