import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from main import app
from models import SessionLocal, HazardZone, DeviceAlertState

client = TestClient(app)

def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "time_utc" in data

def test_device_registration_and_delete():
    dev_id = "test_dev_001"
    reg_payload = {
        "device_id": dev_id,
        "language": "ta",
        "country": "IN",
        "emergency_contacts": [{"name": "Dad", "phone": "+919876543210"}]
    }
    resp = client.post("/api/device/register", json=reg_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "registered"

    # Delete device (privacy)
    del_resp = client.delete(f"/api/device/{dev_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

def test_location_update_deduplication_and_all_clear():
    dev_id = "test_dev_dedup_002"
    now_utc = datetime.now(timezone.utc)
    
    # Insert isolated test hazard zone
    db = SessionLocal()
    test_hz = HazardZone(
        id="test_zone_dedup_loc",
        type="FLOOD",
        severity=3,
        center_lat=13.0827,
        center_lon=80.2707,
        radius_km=5.0,
        start_time=now_utc - timedelta(hours=1),
        end_time=now_utc + timedelta(hours=4),
        source="Test Provider",
        message_key="flood_warning"
    )
    db.add(test_hz)
    db.commit()
    db.close()

    try:
        # 1. First update inside user flood zone (13.0827, 80.2707)
        loc_payload = {"device_id": dev_id, "lat": 13.0827, "lon": 80.2707}
        r1 = client.post("/api/location/update", json=loc_payload)
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["status"] == "DANGEROUS"
        # Must receive a new alert
        assert len(d1["new_alerts"]) >= 1

        # 2. Second update at same location (no spam, deduplicated!)
        r2 = client.post("/api/location/update", json=loc_payload)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["status"] == "DANGEROUS"
        assert len(d2["new_alerts"]) == 0  # Deduplicated!

        # 3. Third update moving far away to safe area (e.g., 13.4, 80.1) -> ALL CLEAR
        safe_loc = {"device_id": dev_id, "lat": 13.4, "lon": 80.1}
        r3 = client.post("/api/location/update", json=safe_loc)
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3["status"] == "SAFE"
        assert d3["all_clear"] is not None
        assert d3["all_clear"]["type"] == "ALL_CLEAR"
    finally:
        db = SessionLocal()
        db.query(HazardZone).filter(HazardZone.id == "test_zone_dedup_loc").delete()
        db.commit()
        db.close()



def test_feature_2_destination_unsafe_check():
    now_utc = datetime.now(timezone.utc)
    db = SessionLocal()
    test_hz = HazardZone(
        id="test_zone_dest_cyclone",
        type="CYCLONE",
        severity=4,
        center_lat=13.0500,
        center_lon=80.2824,
        radius_km=8.0,
        start_time=now_utc - timedelta(hours=1),
        end_time=now_utc + timedelta(hours=4),
        source="GDACS",
        message_key="cyclone_warning"
    )
    db.add(test_hz)
    db.commit()
    db.close()

    try:
        resp = client.post("/api/safety/check?lang=en", json={"lat": 13.0500, "lon": 80.2824})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DANGEROUS"
        assert len(data["zones"]) >= 1
        assert "Destination is currently DANGEROUS" in data["message"]
    finally:
        db = SessionLocal()
        db.query(HazardZone).filter(HazardZone.id == "test_zone_dest_cyclone").delete()
        db.commit()
        db.close()

def test_feature_3_route_unreachable_message():
    now_utc = datetime.now(timezone.utc)
    db = SessionLocal()
    test_hz = HazardZone(
        id="test_zone_dest_barrier",
        type="CYCLONE",
        severity=4,
        center_lat=13.0500,
        center_lon=80.2824,
        radius_km=8.0,
        start_time=now_utc - timedelta(hours=1),
        end_time=now_utc + timedelta(hours=4),
        source="GDACS",
        message_key="cyclone_warning"
    )
    db.add(test_hz)
    db.commit()
    db.close()

    try:
        resp = client.post("/api/route/safe?lang=en", json={
            "origin": [13.0827, 80.2707],
            "destination": [13.0500, 80.2824],
            "profile": "driving-car"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ORIGIN_UNSAFE", "DESTINATION_UNSAFE", "UNREACHABLE")
    finally:
        db = SessionLocal()
        db.query(HazardZone).filter(HazardZone.id == "test_zone_dest_barrier").delete()
        db.commit()
        db.close()


def test_sos_endpoint():
    sos_payload = {
        "device_id": "test_dev_sos",
        "lat": 13.0827,
        "lon": 80.2707
    }
    resp = client.post("/api/sos", json=sos_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "logged"
    assert "EMERGENCY SOS" in data["prefilled_message"]
    assert data["emergency_numbers"]["primary"] == "112"

def test_expired_zone_ignored_in_nearby_hazards():
    # Nearby query should NOT return demo_expired_flood
    resp = client.get("/api/hazards/nearby?lat=13.0400&lon=80.2500&radius_km=20&include_upcoming=true")
    assert resp.status_code == 200
    hazards = resp.json()["hazards"]
    for h in hazards:
        assert h["id"] != "demo_expired_flood"
