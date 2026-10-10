import logging
import time
from typing import List, Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "TravelTechCrisisApp/1.0 (contact@traveltech.example.org)"

# Cache: query -> results
_SEARCH_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_REVERSE_CACHE: Dict[str, Dict[str, Any]] = {}
_LAST_REQUEST_TIME = 0.0

def _rate_limit():
    global _LAST_REQUEST_TIME
    elapsed = time.time() - _LAST_REQUEST_TIME
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _LAST_REQUEST_TIME = time.time()

def search_places(query: str, lang: str = "en", limit: int = 5) -> List[Dict[str, Any]]:
    """Searches places using Nominatim with caching and rate limiting."""
    clean_query = query.strip()
    cache_key = f"{clean_query.lower()}_{lang}_{limit}"
    if cache_key in _SEARCH_CACHE:
        return _SEARCH_CACHE[cache_key]

    _rate_limit()
    params = {
        "q": clean_query,
        "format": "json",
        "limit": limit,
        "accept-language": lang,
        "addressdetails": 1
    }

    try:
        resp = requests.get(NOMINATIM_SEARCH_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)
        resp.raise_for_status()
        raw_list = resp.json()
    except Exception as e:
        logger.error(f"Error searching places for '{query}': {e}")
        raw_list = []

    # If no exact match found, try best-matching token permutations (e.g. city name without typo prefixes)
    if not raw_list and len(clean_query.split()) > 1:
        tokens = [t for t in clean_query.split() if len(t) > 2]
        for token in tokens:
            try:
                fallback_params = {
                    "q": token,
                    "format": "json",
                    "limit": limit,
                    "accept-language": lang,
                    "addressdetails": 1
                }
                _rate_limit()
                fb_resp = requests.get(NOMINATIM_SEARCH_URL, params=fallback_params, headers={"User-Agent": USER_AGENT}, timeout=8)
                if fb_resp.status_code == 200:
                    fb_list = fb_resp.json()
                    if fb_list:
                        raw_list = fb_list
                        break
            except Exception:
                continue

    results = []
    for item in raw_list:
        addr = item.get("address", {})
        city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality") or addr.get("county") or ""
        state = addr.get("state", "")
        country = addr.get("country", "")

        if city and country:
            short_name = f"{city}, {country}"
        elif city and state:
            short_name = f"{city}, {state}"
        elif city:
            short_name = city
        else:
            parts = [p.strip() for p in item.get("display_name", "").split(",") if p.strip()]
            short_name = ", ".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else "")

        results.append({
            "place_id": str(item.get("place_id")),
            "name": item.get("display_name", "").split(",")[0],
            "display_name": item.get("display_name", ""),
            "short_name": short_name,
            "lat": float(item.get("lat")),
            "lon": float(item.get("lon")),
            "type": item.get("type", "place"),
            "importance": item.get("importance", 0.0)
        })

    # Sort results by importance so the closest/most significant match is first
    results.sort(key=lambda x: x.get("importance", 0.0), reverse=True)

    _SEARCH_CACHE[cache_key] = results
    return results

def reverse_geocode(lat: float, lon: float, lang: str = "en") -> Dict[str, Any]:
    """Reverse geocodes coordinates to a readable place name and country code."""
    cache_key = f"{round(lat, 3)}_{round(lon, 3)}_{lang}"
    if cache_key in _REVERSE_CACHE:
        return _REVERSE_CACHE[cache_key]

    _rate_limit()
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "accept-language": lang,
        "addressdetails": 1
    }

    try:
        resp = requests.get(NOMINATIM_REVERSE_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)
        resp.raise_for_status()
        item = resp.json()
    except Exception as e:
        logger.error(f"Error reverse geocoding ({lat}, {lon}): {e}")
        return {"display_name": f"{round(lat, 4)}, {round(lon, 4)}", "country_code": "IN", "city": ""}

    addr = item.get("address", {})
    country_code = addr.get("country_code", "in").upper()
    city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("suburb", "")
    state = addr.get("state", "")
    country = addr.get("country", "")

    if city and country:
        short_name = f"{city}, {country}"
    elif city and state:
        short_name = f"{city}, {state}"
    elif city:
        short_name = city
    else:
        parts = [p.strip() for p in item.get("display_name", "").split(",") if p.strip()]
        short_name = ", ".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else f"{round(lat, 4)}, {round(lon, 4)}")

    result = {
        "display_name": item.get("display_name", f"{round(lat, 4)}, {round(lon, 4)}"),
        "short_name": short_name,
        "country_code": country_code,
        "city": city,
        "state": state,
        "country": country,
        "lat": lat,
        "lon": lon
    }
    _REVERSE_CACHE[cache_key] = result
    return result
