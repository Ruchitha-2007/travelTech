import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Pydantic Schemas
class DeviceRegisterRequest(BaseModel):
    device_id: str
    language: str = "en"
    country: str = "IN"
    emergency_contacts: List[Dict[str, str]] = []

class LocationUpdateRequest(BaseModel):
    device_id: str
    lat: float
    lon: float

class SafetyCheckRequest(BaseModel):
    lat: float
    lon: float

class RouteSafeRequest(BaseModel):
    origin: List[float]  # [lat, lon]
    destination: List[float]  # [lat, lon]
    profile: str = "driving-car"  # driving-car, foot-walking, cycling-regular

class SOSRequest(BaseModel):
    device_id: str
    lat: float
    lon: float
    message: Optional[str] = None

class AdminZoneRequest(BaseModel):
    type: str  # CYCLONE | FLOOD | HEAVY_RAIN | HIGH_WIND | THUNDERSTORM | HEAT | EARTHQUAKE | TSUNAMI | MANUAL
    severity: int = Field(ge=1, le=4)
    center_lat: float
    center_lon: float
    radius_km: float
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    source: str = "Admin: District Authority"
    message_key: str = "flood_warning"
    verified: bool = True

class CrowdReportRequest(BaseModel):
    device_id: Optional[str] = None
    lat: float
    lon: float
    report_type: str
    description: Optional[str] = None

class TripPrecheckRequest(BaseModel):
    lat: float
    lon: float
    days: int = 7
