import json
import logging
from datetime import datetime, timezone, timedelta
from models import SessionLocal, init_db, HazardZone, DeviceAlertState, Device

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_demo")

# Chennai Coordinates
CHENNAI_CENTRAL = (13.0827, 80.2707)
CHENNAI_MARINA = (13.0500, 80.2824)
CHENNAI_AIRPORT = (12.9941, 80.1709)
CHENNAI_TAMBARAM = (12.9249, 80.1000)

def clear_existing(db):
    db.query(HazardZone).delete()
    db.query(DeviceAlertState).delete()
    db.commit()
    logger.info("Cleared previous demo hazard zones and device alert states.")

def seed_scenarios():
    init_db()
    db = SessionLocal()
    clear_existing(db)

    now_utc = datetime.now(timezone.utc)
    one_hour_ago = now_utc - timedelta(hours=1)
    six_hours_later = now_utc + timedelta(hours=6)

    # Scenario A: Flood zone directly over user location (Chennai Central)
    # Severity 3 -> DANGEROUS
    zone_a = HazardZone(
        id="demo_flood_user_loc",
        type="FLOOD",
        severity=3,
        center_lat=CHENNAI_CENTRAL[0],
        center_lon=CHENNAI_CENTRAL[1],
        radius_km=5.0,
        start_time=one_hour_ago,
        end_time=six_hours_later,
        source="Admin: District Disaster Management Authority",
        source_url="https://tnema.tn.gov.in",
        message_key="flood_warning",
        message_params=json.dumps({"name": "Adyar Basin Urban Flash Flood", "level": "Orange"}),
        verified=True
    )

    # Scenario B: Severe Cyclone at destination (Chennai Marina Beach)
    # Severity 4 -> DANGEROUS / DESTINATION_UNSAFE
    zone_b = HazardZone(
        id="demo_cyclone_destination",
        type="CYCLONE",
        severity=4,
        center_lat=CHENNAI_MARINA[0],
        center_lon=CHENNAI_MARINA[1],
        radius_km=8.0,
        start_time=one_hour_ago,
        end_time=six_hours_later,
        source="GDACS",
        source_url="https://www.gdacs.org",
        message_key="cyclone_warning",
        message_params=json.dumps({"name": "Cyclone Vardah Relict", "alertlevel": "Red"}),
        verified=True
    )

    # Scenario C: Hazard on the middle of route between Central and Airport
    # Center at Guindy: 13.0067, 80.2025
    zone_c = HazardZone(
        id="demo_route_midpoint_flood",
        type="FLOOD",
        severity=3,
        center_lat=13.0067,
        center_lon=80.2025,
        radius_km=3.0,
        start_time=one_hour_ago,
        end_time=six_hours_later,
        source="Open-Meteo forecast, updated 14:00",
        source_url="https://open-meteo.com",
        message_key="heavy_rain_hourly",
        message_params=json.dumps({"rain_mm": 65, "severity": 3}),
        verified=False
    )

    # Scenario D: Expired zone (ended 30 mins ago) - MUST BE IGNORED by safety checks
    zone_d_expired = HazardZone(
        id="demo_expired_flood",
        type="FLOOD",
        severity=4,
        center_lat=13.0400,
        center_lon=80.2500,
        radius_km=10.0,
        start_time=now_utc - timedelta(hours=4),
        end_time=now_utc - timedelta(minutes=30),
        source="Admin",
        source_url="",
        message_key="flood_warning",
        message_params=json.dumps({}),
        verified=True
    )

    # Scenario E: Upcoming zone (starts in 3 hours)
    zone_e_upcoming = HazardZone(
        id="demo_upcoming_high_wind",
        type="HIGH_WIND",
        severity=3,
        center_lat=13.1500,
        center_lon=80.2800,
        radius_km=15.0,
        start_time=now_utc + timedelta(hours=3),
        end_time=now_utc + timedelta(hours=8),
        source="Open-Meteo forecast, updated 14:00",
        source_url="https://open-meteo.com",
        message_key="high_wind_hourly",
        message_params=json.dumps({}),
        verified=False
    )

    db.add_all([zone_a, zone_b, zone_c, zone_d_expired, zone_e_upcoming])
    db.commit()
    db.close()
    logger.info("Successfully seeded Chennai demo scenarios (A, B, C, D, E)!")

if __name__ == "__main__":
    seed_scenarios()
