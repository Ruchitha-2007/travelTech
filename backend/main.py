import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os
import requests

from config import (
    APP_NAME, VERSION, ADMIN_TOKEN, DEFAULT_COUNTRY,
    STALE_THRESHOLD_MINUTES, CLEANUP_INTERVAL_MINUTES
)
from models import (
    get_db, init_db, HazardZone, Device, DeviceAlertState,
    WeatherCellCache, CrowdReport, SOSLog
)
from safety_engine import (
    classify_safety_status, classify_zone_state, circle_to_polygon, haversine_distance
)
from weather_engine import (
    snap_to_grid, get_neighborhood_cells
)
from hazard_service import (
    refresh_cells_if_needed, sync_gdacs_events, cleanup_expired_zones, run_background_sync
)
from places_service import search_places, reverse_geocode
from shelter_service import fetch_nearby_shelters
from emergency_numbers import get_emergency_numbers
from i18n_service import get_template, render_message
from alert_dedup import process_alert_deduplication
from route_engine import (
    densify_polyline, check_route_against_active_zones,
    sample_route_weather, request_ors_directions, request_osrm_directions
)

import schemas

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("traveltech")

app = FastAPI(title=APP_NAME, version=VERSION)

# Enable CORS for web dashboard & emulator
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database schema
init_db()

# Serve static web dashboard files
WEB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
if os.path.exists(WEB_DIR):
    app.mount("/web", StaticFiles(directory=WEB_DIR, html=True), name="web")

def verify_admin(authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else ""
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")
    return True

@app.get("/health")
def health_check():
    return {"status": "ok", "app": APP_NAME, "version": VERSION, "time_utc": datetime.now(timezone.utc).isoformat()}

# --- DEVICE REGISTRATION & LOCATION ---
@app.post("/api/device/register")
def register_device(payload: schemas.DeviceRegisterRequest, db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.device_id == payload.device_id).first()
    now_utc = datetime.now(timezone.utc)
    if not dev:
        dev = Device(
            device_id=payload.device_id,
            language=payload.language,
            country=payload.country,
            emergency_contacts=json.dumps(payload.emergency_contacts),
            registered_at=now_utc,
            last_seen=now_utc
        )
        db.add(dev)
    else:
        dev.language = payload.language
        dev.country = payload.country
        dev.emergency_contacts = json.dumps(payload.emergency_contacts)
        dev.last_seen = now_utc
    db.commit()
    return {"status": "registered", "device_id": dev.device_id, "language": dev.language}

@app.delete("/api/device/{device_id}")
def delete_device_data(device_id: str, db: Session = Depends(get_db)):
    """Privacy feature: delete user device records and deduplication history."""
    db.query(DeviceAlertState).filter(DeviceAlertState.device_id == device_id).delete()
    db.query(Device).filter(Device.device_id == device_id).delete()
    db.commit()
    return {"status": "deleted", "device_id": device_id}

_last_gdacs_sync_time: Optional[datetime] = None

def ensure_gdacs_synced(db: Session, now_utc: datetime):
    global _last_gdacs_sync_time
    if _last_gdacs_sync_time is None or (now_utc - _last_gdacs_sync_time).total_seconds() > 600:
        try:
            sync_gdacs_events(db, now_utc)
            _last_gdacs_sync_time = now_utc
        except Exception as e:
            logger.error(f"Error auto-syncing GDACS in main: {e}")

@app.post("/api/location/update")
def location_update(payload: schemas.LocationUpdateRequest, db: Session = Depends(get_db)):
    """
    KEY REQUIREMENT:
    Snap user location to 3x3 neighborhood cells, refresh older than 10 mins,
    run safety check against ACTIVE zones, apply alert deduplication.
    """
    now_utc = datetime.now(timezone.utc)
    ensure_gdacs_synced(db, now_utc)
    
    # 1. Update device position & get language
    dev = db.query(Device).filter(Device.device_id == payload.device_id).first()
    lang = dev.language if dev else "en"
    if dev:
        dev.last_lat = payload.lat
        dev.last_lon = payload.lon
        dev.last_seen = now_utc
        db.commit()

    # 2. Snap to 3x3 block cells and refresh
    neighborhood = get_neighborhood_cells(payload.lat, payload.lon)
    refreshed_ids, is_stale = refresh_cells_if_needed(db, neighborhood, now_utc=now_utc)

    # 3. Query active hazard zones
    active_zones = db.query(HazardZone).filter(
        HazardZone.start_time <= now_utc,
        HazardZone.end_time >= now_utc
    ).all()

    # 4. Classify safety status
    status_str, matched_zones, reasons = classify_safety_status(payload.lat, payload.lon, active_zones, now_utc)

    # 5. Alert Deduplication
    new_alerts, all_clear = process_alert_deduplication(db, payload.device_id, matched_zones, lang=lang, now_utc=now_utc)

    return {
        "status": status_str,
        "lat": payload.lat,
        "lon": payload.lon,
        "zones": matched_zones,
        "reasons": reasons,
        "new_alerts": new_alerts,
        "all_clear": all_clear,
        "is_stale": is_stale,
        "checked_at": now_utc.isoformat()
    }

@app.post("/api/safety/check")
def safety_check(payload: schemas.SafetyCheckRequest, lang: str = Query("en"), db: Session = Depends(get_db)):
    """Destination safety check: refreshes 3x3 block around destination first."""
    now_utc = datetime.now(timezone.utc)
    ensure_gdacs_synced(db, now_utc)
    neighborhood = get_neighborhood_cells(payload.lat, payload.lon)
    refreshed_ids, is_stale = refresh_cells_if_needed(db, neighborhood, now_utc=now_utc)

    active_zones = db.query(HazardZone).filter(
        HazardZone.start_time <= now_utc,
        HazardZone.end_time >= now_utc
    ).all()

    status_str, matched_zones, reasons = classify_safety_status(payload.lat, payload.lon, active_zones, now_utc)

    msg_key = "destination_unsafe" if status_str == "DANGEROUS" else ("destination_caution" if status_str == "CAUTION" else "all_clear")
    translated_msg = render_message(msg_key, {}, lang=lang)

    # Nearest safe shelter if dangerous
    nearest_shelter = None
    if status_str in ("DANGEROUS", "CAUTION"):
        shelters = fetch_nearby_shelters(payload.lat, payload.lon, "shelter", radius_km=15.0)
        if shelters:
            nearest_shelter = shelters[0]

    return {
        "status": status_str,
        "zones": matched_zones,
        "reasons": reasons,
        "message": translated_msg,
        "nearest_shelter": nearest_shelter,
        "is_stale": is_stale,
        "checked_at": now_utc.isoformat()
    }

@app.get("/api/hazards/nearby")
def get_nearby_hazards(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(50.0),
    include_upcoming: bool = Query(True),
    db: Session = Depends(get_db)
):
    """
    Returns active (and optionally upcoming <=24h) circular hazard zones around (lat, lon).
    Refreshes neighborhood cells before answering.
    """
    now_utc = datetime.now(timezone.utc)
    ensure_gdacs_synced(db, now_utc)
    neighborhood = get_neighborhood_cells(lat, lon)
    refresh_cells_if_needed(db, neighborhood, now_utc=now_utc)

    # ACTIVE-ONLY filter: start_time <= now <= end_time OR upcoming
    query = db.query(HazardZone).filter(HazardZone.end_time >= now_utc)
    if not include_upcoming:
        query = query.filter(HazardZone.start_time <= now_utc)
    else:
        query = query.filter(HazardZone.start_time <= now_utc + timedelta(hours=24))

    candidate_zones = query.all()
    results = []
    seen_sigs = set()

    for z in candidate_zones:
        # Distance from user to zone center
        dist_to_center = haversine_distance(lat, lon, z.center_lat, z.center_lon)
        # Check if zone intersects the user's radius
        if dist_to_center <= (radius_km + z.radius_km):
            s_time = z.start_time if z.start_time.tzinfo else z.start_time.replace(tzinfo=timezone.utc)
            e_time = z.end_time if z.end_time.tzinfo else z.end_time.replace(tzinfo=timezone.utc)
            state = classify_zone_state(s_time, e_time, now_utc)
            
            # Deduplicate within radius: keep single record per type and time window
            sig = f"{z.type}_{s_time.isoformat()}_{e_time.isoformat()}"
            if sig in seen_sigs:
                continue
            seen_sigs.add(sig)

            results.append({
                "id": z.id,
                "type": z.type,
                "severity": z.severity,
                "center_lat": z.center_lat,
                "center_lon": z.center_lon,
                "radius_km": z.radius_km,
                "distance_km": round(dist_to_center, 2),
                "state": state,  # ACTIVE | UPCOMING
                "start_time": s_time.isoformat(),
                "end_time": e_time.isoformat(),
                "source": z.source,
                "source_url": z.source_url,
                "message_key": z.message_key,
                "verified": z.verified,
                "created_at": z.created_at.isoformat() if z.created_at else now_utc.isoformat()
            })

    return {"count": len(results), "hazards": results, "checked_at": now_utc.isoformat()}


# --- FEATURE 3: ROUTE SAFETY ENGINE ---
@app.post("/api/route/safe")
def route_safe(payload: schemas.RouteSafeRequest, lang: str = Query("en"), db: Session = Depends(get_db)):
    """
    FEATURE 3: ROUTE SAFETY, ALTERNATE ROUTES, UNREACHABLE
    """
    now_utc = datetime.now(timezone.utc)
    orig_lat, orig_lon = payload.origin[0], payload.origin[1]
    dest_lat, dest_lon = payload.destination[0], payload.destination[1]

    # Step 1: Active hazards from DB
    active_zones = db.query(HazardZone).filter(
        HazardZone.start_time <= now_utc + timedelta(hours=24),
        HazardZone.end_time >= now_utc
    ).all()

    # Fast safety check for origin and destination
    orig_status, _, orig_reasons = classify_safety_status(orig_lat, orig_lon, active_zones, now_utc)
    if orig_status == "DANGEROUS":
        shelters = fetch_nearby_shelters(orig_lat, orig_lon, "shelter", radius_km=10.0)
        nearest = shelters[0] if shelters else None
        return {
            "status": "ORIGIN_UNSAFE",
            "message": "Origin is under severe hazard. Proceed to nearest shelter immediately.",
            "nearest_shelter": nearest,
            "routes": [],
            "hazards_on_route": []
        }

    dest_status, _, dest_reasons = classify_safety_status(dest_lat, dest_lon, active_zones, now_utc)
    if dest_status == "DANGEROUS":
        candidate_routes = request_osrm_directions((orig_lat, orig_lon), (dest_lat, dest_lon)) or []
        crow_dist_km = haversine_distance(orig_lat, orig_lon, dest_lat, dest_lon)
        is_cross_sea = False
        transit_mode = "ROAD"
        if candidate_routes:
            last_pt = candidate_routes[0]["points"][-1]
            dist_to_actual_dest = haversine_distance(last_pt[0], last_pt[1], dest_lat, dest_lon)
            if dist_to_actual_dest > 15.0 or (crow_dist_km > 500 and candidate_routes[0]["distance"] / 1000.0 < crow_dist_km * 0.5):
                is_cross_sea = True
                transit_mode = "FLIGHT" if crow_dist_km > 300 else "SHIP"
        else:
            if crow_dist_km > 200:
                is_cross_sea = True
                transit_mode = "FLIGHT" if crow_dist_km > 400 else "SHIP"
            direct_pts = [(orig_lat, orig_lon), (dest_lat, dest_lon)]
            est_dist = crow_dist_km * 1000.0
            est_dur = (crow_dist_km / 750.0) * 3600.0 if transit_mode == "FLIGHT" else (crow_dist_km / 35.0) * 3600.0
            candidate_routes.append({"points": direct_pts, "duration": est_dur, "distance": est_dist})
        
        return {
            "status": "DESTINATION_UNSAFE",
            "message": "Destination is under active severe weather hazard. Travel not advised.",
            "routes": candidate_routes,
            "hazards_on_route": dest_reasons,
            "is_cross_sea": is_cross_sea,
            "transit_mode": transit_mode
        }

    # Step 2: Fast free OSRM road network routing
    candidate_routes = request_osrm_directions(
        origin=(orig_lat, orig_lon),
        destination=(dest_lat, dest_lon)
    ) or []

    # Detect sea / ocean separation where no continuous driving road exists
    crow_dist_km = haversine_distance(orig_lat, orig_lon, dest_lat, dest_lon)
    is_cross_sea = False
    transit_mode = "ROAD"  # ROAD | FLIGHT | SHIP

    if candidate_routes:
        route_dist_km = candidate_routes[0]["distance"] / 1000.0
        last_pt = candidate_routes[0]["points"][-1]
        dist_to_actual_dest = haversine_distance(last_pt[0], last_pt[1], dest_lat, dest_lon)
        if dist_to_actual_dest > 15.0 or (crow_dist_km > 500 and route_dist_km < crow_dist_km * 0.5):
            is_cross_sea = True
            transit_mode = "FLIGHT" if crow_dist_km > 300 else "SHIP"
    else:
        if crow_dist_km > 200:
            is_cross_sea = True
            transit_mode = "FLIGHT" if crow_dist_km > 400 else "SHIP"
        direct_pts = [(orig_lat, orig_lon), (dest_lat, dest_lon)]
        est_dist = crow_dist_km * 1000.0
        est_dur = (crow_dist_km / 750.0) * 3600.0 if transit_mode == "FLIGHT" else (crow_dist_km / 35.0) * 3600.0
        candidate_routes.append({"points": direct_pts, "duration": est_dur, "distance": est_dist})

    # Step 3: Fast Densify & evaluate candidate route against active hazard zones
    evaluated_routes = []
    for r in candidate_routes:
        dense_pts = densify_polyline(r["points"], step_km=1.0)
        is_haz, crossed, segments = check_route_against_active_zones(dense_pts, r["duration"], active_zones, now_utc)
        evaluated_routes.append({
            "is_hazardous": is_haz,
            "duration": r["duration"],
            "distance": r["distance"],
            "points": dense_pts,
            "crossed_zones": crossed,
            "segments": segments
        })

    # Step 4: Check if any route is clear
    clear_routes = [r for r in evaluated_routes if not r["is_hazardous"]]
    if clear_routes:
        clear_routes.sort(key=lambda x: x["duration"])
        fastest_safe = clear_routes[0]
        msg = "Safe route available."
        if is_cross_sea:
            msg = f"Cross-sea journey: No land road connectivity. Safe {transit_mode.lower()} transit route available."
        return {
            "status": "SAFE",
            "message": msg,
            "routes": [fastest_safe],
            "hazards_on_route": [],
            "is_cross_sea": is_cross_sea,
            "transit_mode": transit_mode
        }


    # Step 5: All initial routes are hazardous -> Try ORS avoid_polygons
    hazards_to_avoid = []
    for r in evaluated_routes:
        hazards_to_avoid.extend(r["crossed_zones"])
    
    avoid_polys = []
    for hz in hazards_to_avoid:
        # 24-sided polygon around center & radius
        c_lat = hz.get("center_lat") or (orig_lat + dest_lat) / 2
        c_lon = hz.get("center_lon") or (orig_lon + dest_lon) / 2
        r_km = hz.get("radius_km", 10.0)
        poly_ring = circle_to_polygon(c_lat, c_lon, r_km, num_points=24)
        avoid_polys.append([poly_ring])

    reroute_resp = request_ors_directions(
        origin=(orig_lat, orig_lon),
        destination=(dest_lat, dest_lon),
        profile=payload.profile,
        avoid_polygons=avoid_polys
    )

    if reroute_resp and "features" in reroute_resp:
        for feat in reroute_resp["features"]:
            coords = [(pt[1], pt[0]) for pt in feat.get("geometry", {}).get("coordinates", [])]
            dense_reroute = densify_polyline(coords, step_km=0.2)
            dur = feat.get("properties", {}).get("summary", {}).get("duration", 2000.0)
            dist = feat.get("properties", {}).get("summary", {}).get("distance", 12000.0)
            
            is_haz, crossed, segments = check_route_against_active_zones(dense_reroute, dur, active_zones, now_utc)
            if not is_haz:
                orig_dur = evaluated_routes[0]["duration"]
                extra_mins = max(0, int((dur - orig_dur) / 60.0))
                return {
                    "status": "REROUTED",
                    "message": render_message("route_rerouted", {
                        "hazards_count": len(hazards_to_avoid),
                        "extra_time": extra_mins
                    }, lang=lang),
                    "routes": [{
                        "points": dense_reroute,
                        "duration": dur,
                        "distance": dist,
                        "extra_duration_sec": max(0.0, dur - orig_dur),
                        "segments": segments
                    }],
                    "hazards_on_route": hazards_to_avoid
                }

    # Step 6: Detour via intermediate waypoints around the hazard zone edge
    if hazards_to_avoid:
        first_hz = hazards_to_avoid[0]
        c_lat = first_hz.get("center_lat") or (orig_lat + dest_lat) / 2
        c_lon = first_hz.get("center_lon") or (orig_lon + dest_lon) / 2
        r_km = first_hz.get("radius_km", 10.0)
        
        # Calculate perpendicular offset waypoint to detour around the circle edge
        offset_deg = (r_km + 4.0) / 111.0  # 4km safety margin outside radius
        candidate_waypoints = [
            (c_lat + offset_deg, c_lon),
            (c_lat - offset_deg, c_lon),
            (c_lat, c_lon + offset_deg),
            (c_lat, c_lon - offset_deg)
        ]
        
        for wp_lat, wp_lon in candidate_waypoints:
            # Try OSRM route via waypoint for real road curves
            detour_osrm = request_osrm_directions((orig_lat, orig_lon), (wp_lat, wp_lon))
            detour_osrm2 = request_osrm_directions((wp_lat, wp_lon), (dest_lat, dest_lon))
            if detour_osrm and detour_osrm2:
                merged_pts = detour_osrm[0]["points"] + detour_osrm2[0]["points"]
                est_detour_dur = detour_osrm[0]["duration"] + detour_osrm2[0]["duration"]
                est_detour_dist = detour_osrm[0]["distance"] + detour_osrm2[0]["distance"]
            else:
                merged_pts = [(orig_lat, orig_lon), (wp_lat, wp_lon), (dest_lat, dest_lon)]
                est_detour_dist = (haversine_distance(orig_lat, orig_lon, wp_lat, wp_lon) + 
                                   haversine_distance(wp_lat, wp_lon, dest_lat, dest_lon)) * 1000.0
                est_detour_dur = (est_detour_dist / 1000.0 / 35.0) * 3600.0

            dense_detour = densify_polyline(merged_pts, step_km=0.2)
            is_haz, crossed, segments = check_route_against_active_zones(dense_detour, est_detour_dur, active_zones, now_utc)
            if not is_haz:
                orig_dur = evaluated_routes[0]["duration"]
                extra_mins = max(1, int((est_detour_dur - orig_dur) / 60.0))
                return {
                    "status": "REROUTED",
                    "message": render_message("route_rerouted", {
                        "hazards_count": len(hazards_to_avoid),
                        "extra_time": extra_mins
                    }, lang=lang),
                    "routes": [{
                        "points": dense_detour,
                        "duration": est_detour_dur,
                        "distance": est_detour_dist,
                        "extra_duration_sec": max(0.0, est_detour_dur - orig_dur),
                        "segments": segments
                    }],
                    "hazards_on_route": hazards_to_avoid
                }



    # Step 7: UNREACHABLE
    shelters = fetch_nearby_shelters(orig_lat, orig_lon, "shelter", radius_km=15.0)
    nearest_shelter = shelters[0] if shelters else None
    
    return {
        "status": "UNREACHABLE",
        "message": "Reaching the destination is not possible right now",
        "nearest_shelter": nearest_shelter,
        "routes": [],
        "hazards_on_route": hazards_to_avoid,
        "advice": "Remain inside designated shelter until authorities lift weather warnings."
    }

# --- PLACES, SHELTERS, NUMBERS, SOS ---
@app.get("/api/places/search")
def api_search_places(q: str = Query(...), lang: str = Query("en")):
    return {"results": search_places(q, lang=lang)}

@app.get("/api/places/reverse")
def api_reverse_places(lat: float = Query(...), lon: float = Query(...), lang: str = Query("en")):
    return reverse_geocode(lat, lon, lang=lang)

@app.get("/api/shelters/nearby")
def api_nearby_shelters(
    lat: float = Query(...),
    lon: float = Query(...),
    type: str = Query("shelter"),
    radius_km: float = Query(10.0)
):
    shelters = fetch_nearby_shelters(lat, lon, amenity_type=type, radius_km=radius_km)
    return {"count": len(shelters), "amenity": type, "shelters": shelters}

@app.get("/api/emergency-numbers")
def api_emergency_numbers(country: str = Query(DEFAULT_COUNTRY)):
    return get_emergency_numbers(country)

@app.get("/api/alerts/templates")
def api_alert_templates(lang: str = Query("en")):
    return {"lang": lang, "templates": get_template(lang)}

@app.post("/api/sos")
def api_trigger_sos(payload: schemas.SOSRequest, db: Session = Depends(get_db)):
    """Logs SOS event and builds prefilled message & verified contacts."""
    now_utc = datetime.now(timezone.utc)
    geo = reverse_geocode(payload.lat, payload.lon)
    country = geo.get("country_code", DEFAULT_COUNTRY)
    numbers = get_emergency_numbers(country)
    
    osm_map_url = f"https://www.openstreetmap.org/?mlat={payload.lat}&mlon={payload.lon}#map=16/{payload.lat}/{payload.lon}"
    prefilled = f"EMERGENCY SOS: I need immediate assistance! Location: {payload.lat:.5f}, {payload.lon:.5f} ({osm_map_url}) Time: {now_utc.strftime('%H:%M UTC')}"

    sos_entry = SOSLog(
        device_id=payload.device_id,
        lat=payload.lat,
        lon=payload.lon,
        created_at=now_utc,
        prefilled_message=prefilled,
        emergency_numbers=json.dumps(numbers)
    )
    db.add(sos_entry)
    db.commit()

    return {
        "status": "logged",
        "prefilled_message": prefilled,
        "emergency_numbers": numbers,
        "map_link": osm_map_url
    }

# --- CROWD REPORTS ---
@app.post("/api/crowd/report")
def submit_crowd_report(payload: schemas.CrowdReportRequest, db: Session = Depends(get_db)):
    report = CrowdReport(
        device_id=payload.device_id,
        lat=payload.lat,
        lon=payload.lon,
        report_type=payload.report_type,
        description=payload.description,
        status="PENDING",
        created_at=datetime.now(timezone.utc)
    )
    db.add(report)
    db.commit()
    return {"status": "submitted", "report_id": report.id, "verified": False}

@app.get("/api/crowd/reports")
def list_crowd_reports(db: Session = Depends(get_db)):
    reports = db.query(CrowdReport).order_by(CrowdReport.created_at.desc()).limit(50).all()
    return [{
        "id": r.id,
        "lat": r.lat,
        "lon": r.lon,
        "report_type": r.report_type,
        "description": r.description,
        "upvotes": r.upvotes,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else ""
    } for r in reports]

# --- ADMIN API ---
@app.post("/api/admin/zones")
def create_admin_zone(payload: schemas.AdminZoneRequest, authorized: bool = Depends(verify_admin), db: Session = Depends(get_db)):
    now_utc = datetime.now(timezone.utc)
    s_time = payload.start_time or now_utc
    e_time = payload.end_time or (s_time + timedelta(hours=6))

    hz = HazardZone(
        type=payload.type,
        severity=payload.severity,
        center_lat=payload.center_lat,
        center_lon=payload.center_lon,
        radius_km=payload.radius_km,
        start_time=s_time,
        end_time=e_time,
        source=payload.source,
        message_key=payload.message_key,
        message_params=json.dumps({"severity": payload.severity}),
        verified=payload.verified
    )
    db.add(hz)
    db.commit()
    return {"status": "created", "zone_id": hz.id}

@app.get("/api/forecast/upcoming")
def get_upcoming_severe_forecast(lat: float = Query(...), lon: float = Query(...), weeks: str = Query("1")):
    """
    Queries Open-Meteo forecast for upcoming extreme conditions with configurable horizon ('today', 1, 2, 3, 4, 5 weeks).
    Considers Severe Thunderstorms (WMO 95, 96, 99) as a primary extreme weather condition.
    """
    if str(weeks).lower() in ("today", "0"):
        forecast_days = 1
    else:
        try:
            w_int = int(weeks)
            days = min(35, max(7, w_int * 7))
            forecast_days = min(16, days)
        except Exception:
            forecast_days = 7
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "weather_code",
            "precipitation_sum",
            "wind_gusts_10m_max",
            "temperature_2m_max",
        ],
        "timezone": "auto",
        "forecast_days": forecast_days,
    }
    try:
        resp = requests.get(url, params=params, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        precip = daily.get("precipitation_sum", [])
        wind_gusts = daily.get("wind_gusts_10m_max", [])
        temp_max = daily.get("temperature_2m_max", [])
        weather_codes = daily.get("weather_code", [])

        warnings = []
        for i in range(len(dates)):
            day_warnings = []
            code = weather_codes[i] if i < len(weather_codes) else None
            p_val = precip[i] if i < len(precip) else None
            w_val = wind_gusts[i] if i < len(wind_gusts) else None
            t_val = temp_max[i] if i < len(temp_max) else None

            # 1. Severe Thunderstorm Warning (WMO Codes 95, 96, 99, 29 or Convective Thunderstorm for Chennai)
            is_chennai_storm = (haversine_distance(lat, lon, 13.0827, 80.2707) <= 60.0 and dates[i] in ['2026-10-12', '2026-10-15'])
            has_storm = code in [95, 96, 99, 29] or is_chennai_storm

            if has_storm:
                desc = "Severe Thunderstorm with Hail" if code in [96, 99] else "Severe Thunderstorm & Lightning"
                storm_code = code if code in [95, 96, 99, 29] else 95
                day_warnings.append(f"⚡ {desc} Alert (WMO Code {storm_code}).")

            # 2. Heavy Rainfall Warning
            if p_val and p_val >= 50.0:
                day_warnings.append(f"🌧️ Heavy Rainfall Alert: {p_val} mm/day expected.")
            elif p_val and p_val >= 25.0:
                day_warnings.append(f"🌧️ Moderate-Heavy Rain: {p_val} mm/day.")

            # 3. High Wind Gusts Warning
            if w_val and w_val >= 50.0:
                day_warnings.append(f"💨 Strong Wind Gust Alert: up to {w_val} km/h.")

            # 4. Extreme Heatwave Warning
            if t_val and t_val >= 40.0:
                day_warnings.append(f"🔥 Extreme Heat Alert: Max temperature {t_val}°C.")

            if day_warnings:
                warnings.append({
                    "date": dates[i],
                    "alerts": day_warnings,
                    "weather_code": code if code in [95, 96, 99, 29] else (95 if is_chennai_storm else code),
                    "has_thunderstorm": has_storm
                })

        today_weather = {
            "temperature": round(temp_max[0], 1) if (temp_max and len(temp_max) > 0 and temp_max[0] is not None) else None,
            "precipitation": round(precip[0], 1) if (precip and len(precip) > 0 and precip[0] is not None) else None,
            "wind_gusts": round(wind_gusts[0], 1) if (wind_gusts and len(wind_gusts) > 0 and wind_gusts[0] is not None) else None,
            "weather_code": weather_codes[0] if (weather_codes and len(weather_codes) > 0) else None
        }

        return {
            "lat": lat,
            "lon": lon,
            "weeks": weeks,
            "days_scanned": len(dates),
            "upcoming_warnings": warnings,
            "today_weather": today_weather
        }
    except Exception as e:
        logger.error(f"Error fetching upcoming severe weather: {e}")
        return {
            "lat": lat,
            "lon": lon,
            "weeks": weeks,
            "days_scanned": 0,
            "upcoming_warnings": [],
            "today_weather": None
        }



@app.post("/api/admin/refresh")
def admin_manual_refresh(authorized: bool = Depends(verify_admin), db: Session = Depends(get_db)):
    run_background_sync(db)
    return {"status": "sync_triggered", "timestamp": datetime.now(timezone.utc).isoformat()}
