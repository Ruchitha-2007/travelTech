import pytest
from datetime import datetime, timedelta, timezone
from safety_engine import (
    haversine_distance, is_point_in_circle, circle_to_polygon,
    classify_zone_state, classify_safety_status
)

def test_haversine_distance():
    # Chennai Central to Chennai Airport: ~18-19 km
    central_lat, central_lon = 13.0827, 80.2707
    airport_lat, airport_lon = 12.9941, 80.1709
    dist = haversine_distance(central_lat, central_lon, airport_lat, airport_lon)
    assert 14.0 < dist < 18.0

    # Same point distance should be 0.0
    assert haversine_distance(central_lat, central_lon, central_lat, central_lon) == 0.0

def test_is_point_in_circle():
    # Center at 13.0, 80.0
    c_lat, c_lon = 13.0, 80.0
    radius_km = 10.0
    
    # Point very close (~1 km away)
    assert is_point_in_circle(13.008, 80.0, c_lat, c_lon, radius_km) is True
    # Point far away (~50 km away)
    assert is_point_in_circle(13.45, 80.0, c_lat, c_lon, radius_km) is False

def test_circle_to_polygon():
    poly = circle_to_polygon(13.0827, 80.2707, 15.0, num_points=24)
    assert len(poly) == 25  # 24 vertices + 1 closing vertex
    # First and last coordinate must match (closed polygon)
    assert poly[0] == poly[-1]
    # Check [lon, lat] format
    for pt in poly:
        assert isinstance(pt[0], float)
        assert isinstance(pt[1], float)
        assert 79.5 < pt[0] < 81.0
        assert 12.5 < pt[1] < 13.5

def test_active_only_rule_classification():
    now = datetime.now(timezone.utc)
    
    # Active: started 1h ago, ends in 2h
    assert classify_zone_state(now - timedelta(hours=1), now + timedelta(hours=2), now) == "ACTIVE"
    
    # Expired: ended 10 mins ago
    assert classify_zone_state(now - timedelta(hours=3), now - timedelta(minutes=10), now) == "EXPIRED"
    
    # Upcoming: starts in 3h, ends in 6h (within 24h)
    assert classify_zone_state(now + timedelta(hours=3), now + timedelta(hours=6), now) == "UPCOMING"
    
    # Future (> 24h away)
    assert classify_zone_state(now + timedelta(hours=25), now + timedelta(hours=30), now) == "FUTURE"

def test_safety_classification_statuses():
    now = datetime.now(timezone.utc)
    
    zone_flood_danger = {
        "id": "z1",
        "type": "FLOOD",
        "severity": 3,
        "center_lat": 13.0827,
        "center_lon": 80.2707,
        "radius_km": 10.0,
        "start_time": now - timedelta(hours=1),
        "end_time": now + timedelta(hours=2),
        "source": "GDACS"
    }
    
    zone_rain_caution = {
        "id": "z2",
        "type": "HEAVY_RAIN",
        "severity": 2,
        "center_lat": 13.0827,
        "center_lon": 80.2707,
        "radius_km": 10.0,
        "start_time": now - timedelta(hours=1),
        "end_time": now + timedelta(hours=2),
        "source": "Open-Meteo"
    }

    # 1. Point inside severity 3 zone -> DANGEROUS
    status, zones, reasons = classify_safety_status(13.0827, 80.2707, [zone_flood_danger], now)
    assert status == "DANGEROUS"
    assert len(zones) == 1
    
    # 2. Point inside severity 2 zone only -> CAUTION
    status, zones, reasons = classify_safety_status(13.0827, 80.2707, [zone_rain_caution], now)
    assert status == "CAUTION"
    assert len(zones) == 1

    # 3. Point far outside zones -> SAFE
    status, zones, reasons = classify_safety_status(13.50, 80.90, [zone_flood_danger, zone_rain_caution], now)
    assert status == "SAFE"
    assert len(zones) == 0

def test_expired_and_upcoming_zones_ignored_in_active_safety():
    now = datetime.now(timezone.utc)
    
    expired_zone = {
        "id": "z_exp",
        "type": "FLOOD",
        "severity": 4,
        "center_lat": 13.0827,
        "center_lon": 80.2707,
        "radius_km": 10.0,
        "start_time": now - timedelta(hours=5),
        "end_time": now - timedelta(hours=1),
        "source": "GDACS"
    }
    
    upcoming_zone = {
        "id": "z_up",
        "type": "CYCLONE",
        "severity": 4,
        "center_lat": 13.0827,
        "center_lon": 80.2707,
        "radius_km": 10.0,
        "start_time": now + timedelta(hours=2),
        "end_time": now + timedelta(hours=8),
        "source": "GDACS"
    }

    # At current location, user has an expired zone and an upcoming zone.
    # Active classification must ignore both and return SAFE!
    status, zones, reasons = classify_safety_status(13.0827, 80.2707, [expired_zone, upcoming_zone], now)
    assert status == "SAFE"
    assert len(zones) == 0
