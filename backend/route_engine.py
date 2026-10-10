import math
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Optional
import polyline
import requests
from config import ORS_API_KEY
from safety_engine import haversine_distance, is_point_in_circle, circle_to_polygon, classify_zone_state
from weather_engine import snap_to_grid, fetch_open_meteo_batch, parse_cell_hazards
from i18n_service import render_message

logger = logging.getLogger(__name__)

ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions"

def densify_polyline(points: List[Tuple[float, float]], step_km: float = 0.2) -> List[Tuple[float, float]]:
    """
    Densifies a polyline list of (lat, lon) so that consecutive points
    are separated by no more than step_km (default 200 meters).
    """
    if len(points) < 2:
        return points

    dense_points = [points[0]]
    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]
        dist = haversine_distance(p1[0], p1[1], p2[0], p2[1])
        if dist > step_km:
            num_sub = int(math.ceil(dist / step_km))
            for j in range(1, num_sub):
                frac = j / num_sub
                inter_lat = p1[0] + frac * (p2[0] - p1[0])
                inter_lon = p1[1] + frac * (p2[1] - p1[1])
                dense_points.append((round(inter_lat, 6), round(inter_lon, 6)))
        dense_points.append(p2)
    return dense_points

def check_route_against_active_zones(
    sampled_points: List[Tuple[float, float]],
    total_duration_sec: float,
    active_zones: List[Any],
    start_time_utc: Optional[datetime] = None
) -> Tuple[bool, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Checks if densified points along the route intersect any active hazard zones (severity >= 3).
    ACTIVE-ONLY & TIME-AWARE RULE:
    Calculates estimated arrival time at each sample point along the route.
    Ignores zones whose end_time is before the user reaches that part of the route.
    Includes zones starting later during the journey.
    Returns (is_hazardous, crossed_zones, route_segments_info).
    """
    if start_time_utc is None:
        start_time_utc = datetime.now(timezone.utc)

    num_samples = len(sampled_points)
    is_hazardous = False
    crossed_zones_map = {}
    segments_info = []

    for idx, (p_lat, p_lon) in enumerate(sampled_points):
        fraction = idx / max(1, num_samples - 1)
        est_arrival = start_time_utc + timedelta(seconds=fraction * total_duration_sec)
        
        pt_has_danger = False
        pt_hazards = []

        for z in active_zones:
            c_lat = z.center_lat if hasattr(z, 'center_lat') else z.get('center_lat')
            c_lon = z.center_lon if hasattr(z, 'center_lon') else z.get('center_lon')
            radius = z.radius_km if hasattr(z, 'radius_km') else z.get('radius_km')
            sev = z.severity if hasattr(z, 'severity') else z.get('severity')
            s_time = z.start_time if hasattr(z, 'start_time') else z.get('start_time')
            e_time = z.end_time if hasattr(z, 'end_time') else z.get('end_time')
            
            if s_time.tzinfo is None:
                s_time = s_time.replace(tzinfo=timezone.utc)
            if e_time.tzinfo is None:
                e_time = e_time.replace(tzinfo=timezone.utc)

            # Arrival time check: zone must be active at the moment user arrives
            if not (s_time <= est_arrival <= e_time):
                continue

            dist = haversine_distance(p_lat, p_lon, c_lat, c_lon)
            if dist <= radius:
                z_id = str(z.id if hasattr(z, 'id') else z.get('id'))
                crossed_zones_map[z_id] = {
                    "id": z_id,
                    "type": z.type if hasattr(z, 'type') else z.get('type'),
                    "severity": sev,
                    "distance_km": round(dist, 2),
                    "source": z.source if hasattr(z, 'source') else z.get('source'),
                    "arrival_time": est_arrival.isoformat()
                }
                pt_hazards.append(z_id)
                if sev >= 3:
                    pt_has_danger = True
                    is_hazardous = True

        segments_info.append({
            "lat": p_lat,
            "lon": p_lon,
            "is_dangerous": pt_has_danger,
            "hazards": pt_hazards
        })

    return is_hazardous, list(crossed_zones_map.values()), segments_info

def sample_route_weather(
    sampled_points: List[Tuple[float, float]],
    duration_sec: float,
    start_time_utc: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    Picks weather sample points along the route every 15-20 km
    (including start, end, midpoint; capped at 12), snaps them to grid cells,
    fetches Open-Meteo in ONE batched call, and creates weather hazard zones.
    """
    if not sampled_points:
        return []
    if start_time_utc is None:
        start_time_utc = datetime.now(timezone.utc)

    # Calculate total route distance
    total_km = 0.0
    for i in range(len(sampled_points) - 1):
        total_km += haversine_distance(sampled_points[i][0], sampled_points[i][1],
                                       sampled_points[i+1][0], sampled_points[i+1][1])

    # Select candidate indices
    step_samples = max(1, int(len(sampled_points) * (18.0 / max(total_km, 18.0))))
    indices = list(range(0, len(sampled_points), step_samples))
    if len(sampled_points) - 1 not in indices:
        indices.append(len(sampled_points) - 1)
    
    # Cap at 12 sample points
    if len(indices) > 12:
        step = len(indices) / 12
        indices = [indices[int(i * step)] for i in range(12)]

    cell_tuples = []
    seen_cells = set()
    for idx in indices:
        pt = sampled_points[idx]
        c_lat, c_lon, cell_id = snap_to_grid(pt[0], pt[1])
        if cell_id not in seen_cells:
            seen_cells.add(cell_id)
            cell_tuples.append((c_lat, c_lon, cell_id))

    if not cell_tuples:
        return []

    forecasts = fetch_open_meteo_batch(cell_tuples)
    discovered_hazards = []
    for c_lat, c_lon, cell_id in cell_tuples:
        data = forecasts.get(cell_id)
        if data:
            hazards = parse_cell_hazards(c_lat, c_lon, cell_id, data, start_time_utc)
            discovered_hazards.extend(hazards)

    return discovered_hazards

def request_ors_directions(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    profile: str = "driving-car",
    avoid_polygons: Optional[List[List[List[float]]]] = None
) -> Optional[Dict[str, Any]]:
    """
    Queries OpenRouteService Directions API.
    Coordinates order in ORS is [longitude, latitude].
    """
    if not ORS_API_KEY:
        logger.warning("ORS_API_KEY is not set. Cannot call live ORS.")
        return None

    url = f"{ORS_DIRECTIONS_URL}/{profile}/geojson"
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "TravelTech/1.0"
    }
    body: Dict[str, Any] = {
        "coordinates": [
            [origin[1], origin[0]],         # [lon, lat]
            [destination[1], destination[0]]  # [lon, lat]
        ],
        "alternative_routes": {
            "target_count": 3
        }
    }

    if avoid_polygons:
        body["options"] = {
            "avoid_polygons": {
                "type": "MultiPolygon",
                "coordinates": avoid_polygons
            }
        }

    try:
        resp = requests.post(url, json=body, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"ORS Directions returned {resp.status_code}: {resp.text}")
        return None
    except Exception as e:
        logger.error(f"Error querying ORS Directions: {e}")
        return None

def request_osrm_directions(
    origin: Tuple[float, float],
    destination: Tuple[float, float]
) -> Optional[List[Dict[str, Any]]]:
    """
    100% FREE fallback routing using OpenStreetMap OSRM routing engine.
    Fetches real road network polylines (not straight lines) with 0 API keys needed.
    Coordinates order in OSRM URL: {lon},{lat};{lon},{lat}
    """
    osrm_url = f"https://router.project-osrm.org/route/v1/driving/{origin[1]},{origin[0]};{destination[1]},{destination[0]}?overview=full&geometries=geojson&alternatives=true"
    headers = {"User-Agent": "TravelTech/1.0 (contact@traveltech.example.org)"}
    try:
        resp = requests.get(osrm_url, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            routes = []
            for r in data.get("routes", []):
                coords = r.get("geometry", {}).get("coordinates", [])
                # Convert [lon, lat] -> (lat, lon)
                lat_lon_pts = [(pt[1], pt[0]) for pt in coords]
                dur = r.get("duration", 1800.0)
                dist = r.get("distance", 10000.0)
                if lat_lon_pts:
                    routes.append({"points": lat_lon_pts, "duration": dur, "distance": dist})
            if routes:
                return routes
    except Exception as e:
        logger.warning(f"OSRM Directions error: {e}")
    return None

