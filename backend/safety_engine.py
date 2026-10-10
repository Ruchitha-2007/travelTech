import math
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the great-circle distance (in kilometers) between two latitude/longitude points
    using the Haversine formula.
    """
    R = 6371.0  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def is_point_in_circle(lat: float, lon: float, center_lat: float, center_lon: float, radius_km: float) -> bool:
    """Determines whether a point is inside a circle of given radius (in km)."""
    return haversine_distance(lat, lon, center_lat, center_lon) <= radius_km

def circle_to_polygon(center_lat: float, center_lon: float, radius_km: float, num_points: int = 24) -> List[List[float]]:
    """
    Converts a circular zone to an N-sided polygon [lon, lat] coordinates (GeoJSON style).
    Used ONLY when passing avoid_polygons to OpenRouteService Directions API.
    """
    R = 6371.0
    coords = []
    center_lat_rad = math.radians(center_lat)
    center_lon_rad = math.radians(center_lon)
    angular_dist = radius_km / R

    for i in range(num_points):
        bearing = math.radians(360.0 * i / num_points)
        lat_rad = math.asin(
            math.sin(center_lat_rad) * math.cos(angular_dist) +
            math.cos(center_lat_rad) * math.sin(angular_dist) * math.cos(bearing)
        )
        lon_rad = center_lon_rad + math.atan2(
            math.sin(bearing) * math.sin(angular_dist) * math.cos(center_lat_rad),
            math.cos(angular_dist) - math.sin(center_lat_rad) * math.sin(lat_rad)
        )
        # ORS expects [longitude, latitude]
        coords.append([round(math.degrees(lon_rad), 6), round(math.degrees(lat_rad), 6)])
    
    # Close polygon ring
    if coords:
        coords.append(coords[0])
    return coords

def classify_zone_state(start_time: datetime, end_time: datetime, now_utc: Optional[datetime] = None) -> str:
    """
    ACTIVE-ONLY RULE:
    ACTIVE   = start_time <= now <= end_time
    UPCOMING = now < start_time <= now + 24 hours
    EXPIRED  = end_time < now
    FUTURE   = start_time > now + 24 hours
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    
    # Ensure timezone awareness
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    if end_time < now_utc:
        return "EXPIRED"
    elif start_time <= now_utc <= end_time:
        return "ACTIVE"
    elif now_utc < start_time:
        diff_hours = (start_time - now_utc).total_seconds() / 3600.0
        if diff_hours <= 24.0:
            return "UPCOMING"
        return "FUTURE"
    return "EXPIRED"

def classify_safety_status(lat: float, lon: float, active_zones: List[Any], now_utc: Optional[datetime] = None) -> Tuple[str, List[Dict[str, Any]], List[str]]:
    """
    Evaluates safety status for a point against ACTIVE hazard zones.
    - DANGEROUS if inside any active zone with severity >= 3
    - CAUTION if inside any active zone with severity == 2
    - SAFE otherwise
    Returns (status, matched_zones_list, reasons_list)
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    matched_zones = []
    reasons = []
    max_severity = 1

    for zone in active_zones:
        # Check active status strictly
        start_time = zone.start_time if hasattr(zone, 'start_time') else zone.get('start_time')
        end_time = zone.end_time if hasattr(zone, 'end_time') else zone.get('end_time')
        
        state = classify_zone_state(start_time, end_time, now_utc)
        if state != "ACTIVE":
            continue

        c_lat = zone.center_lat if hasattr(zone, 'center_lat') else zone.get('center_lat')
        c_lon = zone.center_lon if hasattr(zone, 'center_lon') else zone.get('center_lon')
        radius = zone.radius_km if hasattr(zone, 'radius_km') else zone.get('radius_km')
        severity = zone.severity if hasattr(zone, 'severity') else zone.get('severity')
        z_type = zone.type if hasattr(zone, 'type') else zone.get('type')
        z_source = zone.source if hasattr(zone, 'source') else zone.get('source')
        z_id = zone.id if hasattr(zone, 'id') else zone.get('id')

        dist = haversine_distance(lat, lon, c_lat, c_lon)
        if dist <= radius:
            zone_dict = {
                "id": str(z_id),
                "type": z_type,
                "severity": severity,
                "center_lat": c_lat,
                "center_lon": c_lon,
                "radius_km": radius,
                "distance_km": round(dist, 2),
                "source": z_source,
                "start_time": start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time),
                "end_time": end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time),
            }
            # Deduplicate by (type, source, severity)
            sig = f"{z_type}_{z_source}_{severity}"
            if not any(m.get("_sig") == sig for m in matched_zones):
                zone_dict["_sig"] = sig
                matched_zones.append(zone_dict)
                reasons.append(f"Inside {z_type} zone ({z_source}) of severity {severity} (dist: {round(dist, 1)}km <= {radius}km)")
            if severity > max_severity:
                max_severity = severity

    # Remove internal _sig tag before returning
    for m in matched_zones:
        m.pop("_sig", None)

    if max_severity >= 3:
        status = "DANGEROUS"
    elif max_severity == 2:
        status = "CAUTION"
    else:
        status = "SAFE"

    return status, matched_zones, reasons

