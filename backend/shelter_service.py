import json
import logging
from typing import List, Dict, Any, Optional
import requests
from safety_engine import haversine_distance

logger = logging.getLogger(__name__)

# Primary & fallback Overpass endpoints
OVERPASS_ENDPOINTS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

USER_AGENT = "TravelTechCrisisApp/1.0 (contact@traveltech.example.org)"

# In-memory LRU-like cache for shelters: (type, round(lat, 2), round(lon, 2), radius_km) -> [results]
_SHELTER_CACHE: Dict[str, List[Dict[str, Any]]] = {}

def fetch_nearby_shelters(lat: float, lon: float, amenity_type: str = "shelter", radius_km: float = 10.0) -> List[Dict[str, Any]]:
    """
    Queries OpenStreetMap Overpass API for shelters, hospitals, or police stations
    around (lat, lon) within radius_km.
    Amenity types: 'shelter', 'hospital', 'police'
    Cached in memory to respect OSM usage policies.
    """
    cache_key = f"{amenity_type}_{round(lat, 2)}_{round(lon, 2)}_{round(radius_km, 1)}"
    if cache_key in _SHELTER_CACHE:
        return _SHELTER_CACHE[cache_key]

    radius_meters = int(radius_km * 1000)
    
    # Overpass amenity query
    if amenity_type == "hospital":
        osm_filter = 'node["amenity"="hospital"]'
    elif amenity_type == "police":
        osm_filter = 'node["amenity"="police"]'
    else:
        # Generic shelter / emergency / community centre
        osm_filter = 'node["amenity"~"shelter|social_facility|community_centre"]'

    overpass_query = f"""
    [out:json][timeout:15];
    ({osm_filter}(around:{radius_meters},{lat},{lon}););
    out body 25;
    """

    data = None
    endpoint = OVERPASS_ENDPOINTS[0]
    try:
        resp = requests.get(
            endpoint,
            params={"data": overpass_query},
            headers={"User-Agent": USER_AGENT},
            timeout=2.0
        )
        if resp.status_code == 200:
            data = resp.json()
    except Exception as e:
        logger.warning(f"Overpass shelter query skipped or timed out: {e}")

    results = []
    if data and "elements" in data:
        for el in data["elements"]:
            el_lat = el.get("lat")
            el_lon = el.get("lon")
            if el_lat is None or el_lon is None:
                continue
            
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("description") or f"Emergency {amenity_type.capitalize()}"
            phone = tags.get("phone") or tags.get("contact:phone") or ""
            dist = haversine_distance(lat, lon, el_lat, el_lon)

            results.append({
                "id": f"osm_{el.get('id')}",
                "name": name,
                "type": amenity_type,
                "lat": el_lat,
                "lon": el_lon,
                "distance_km": round(dist, 2),
                "phone": phone,
                "address": tags.get("addr:street", tags.get("addr:full", ""))
            })

    # Sort results by distance ascending
    results.sort(key=lambda x: x["distance_km"])
    _SHELTER_CACHE[cache_key] = results
    return results
