import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Basic App Config
APP_NAME = "TravelTech Crisis Communication API"
VERSION = "1.0.0"
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./traveltech.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "traveltech_admin_secret_token_2026")
ORS_API_KEY = os.getenv("ORS_API_KEY", "")
DEFAULT_COUNTRY = os.getenv("DEFAULT_COUNTRY", "IN")

# Active time rule & cleanup
CLEANUP_INTERVAL_MINUTES = 5
CELL_CACHE_TTL_MINUTES = 10
STALE_THRESHOLD_MINUTES = 30
UPCOMING_WINDOW_HOURS = 24

# User-Centered Grid Engine Config
GRID_CELL_SIZE_DEG = 0.1  # ~11 km at equator
GRID_CELL_RADIUS_KM = 15.0  # Cell center radius margin

# GDACS Radius Mapping (km) by event type and alert level
# Types: TC (Cyclone), FL (Flood), EQ (Earthquake), TS (Tsunami), VO (Volcano), DR (Drought), WF (Wildfire)
GDACS_RADIUS_CONFIG: Dict[str, Dict[str, float]] = {
    "TC": {"Green": 100.0, "Orange": 200.0, "Red": 300.0},
    "FL": {"Green": 20.0, "Orange": 35.0, "Red": 50.0},
    "EQ": {"Green": 30.0, "Orange": 60.0, "Red": 120.0},
    "TS": {"Green": 50.0, "Orange": 100.0, "Red": 200.0},
    "DEFAULT": {"Green": 20.0, "Orange": 50.0, "Red": 100.0}
}

# Open-Meteo Weather Thresholds
# Hourly thresholds
HOURLY_RAIN_SEV2 = 10.0  # mm/h
HOURLY_RAIN_SEV3 = 30.0  # mm/h
HOURLY_RAIN_SEV4 = 50.0  # mm/h

# Rolling 3-hour precipitation thresholds
ROLLING_3H_RAIN_SEV3 = 50.0   # mm
ROLLING_3H_RAIN_SEV4 = 100.0  # mm

# Daily thresholds (used for 7-day pre-check / upcoming)
DAILY_RAIN_SEV3 = 50.0   # mm/day
DAILY_RAIN_SEV4 = 100.0  # mm/day

# Wind gusts (km/h)
WIND_GUST_SEV2 = 50.0
WIND_GUST_SEV3 = 70.0
WIND_GUST_SEV4 = 90.0

# Heatwave (°C)
HEAT_SEV2 = 40.0
HEAT_SEV3 = 45.0

# WMO Weather Codes for Thunderstorm
WMO_THUNDERSTORM_SEV2 = [95]
WMO_THUNDERSTORM_SEV3 = [96, 99]

# Pre-warmed Monitored Cities (lat, lon, name)
MONITORED_CITIES = [
    {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    {"name": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    {"name": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    {"name": "Visakhapatnam", "lat": 17.6868, "lon": 83.2185},
    {"name": "Kochi", "lat": 9.9312, "lon": 76.2673},
    {"name": "Puducherry", "lat": 11.9416, "lon": 79.8083},
    {"name": "Goa", "lat": 15.2993, "lon": 74.1240},
    {"name": "Bhubaneswar", "lat": 20.2961, "lon": 85.8245},
    {"name": "Delhi", "lat": 28.6139, "lon": 77.2090},
]
