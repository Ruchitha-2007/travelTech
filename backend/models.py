import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, create_engine
)
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DATABASE_URL

Base = declarative_base()

def get_utc_now():
    return datetime.now(timezone.utc)

class HazardZone(Base):
    __tablename__ = "hazard_zones"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    type = Column(String(32), nullable=False)  # CYCLONE | FLOOD | HEAVY_RAIN | HIGH_WIND | THUNDERSTORM | HEAT | EARTHQUAKE | TSUNAMI | MANUAL
    severity = Column(Integer, nullable=False)  # 1: Info, 2: Caution, 3: Danger, 4: Extreme
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False)
    
    # Times stored in UTC
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    
    source = Column(String(64), nullable=False)  # GDACS | Open-Meteo | Admin
    source_url = Column(String(512), nullable=True)
    message_key = Column(String(64), nullable=False)
    message_params = Column(Text, nullable=True)  # JSON-encoded dict or string
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    verified = Column(Boolean, default=False)
    
    # Cell tracking (e.g., "13.1_80.3") for fast cell replacement
    cell_id = Column(String(32), nullable=True, index=True)

class Device(Base):
    __tablename__ = "devices"

    device_id = Column(String(64), primary_key=True)
    language = Column(String(10), default="en")
    country = Column(String(10), default="IN")
    emergency_contacts = Column(Text, nullable=True)  # JSON list
    last_lat = Column(Float, nullable=True)
    last_lon = Column(Float, nullable=True)
    last_seen = Column(DateTime(timezone=True), default=get_utc_now)
    registered_at = Column(DateTime(timezone=True), default=get_utc_now)

class DeviceAlertState(Base):
    """Alert Deduplication: tracks (device_id, zone_id, severity)"""
    __tablename__ = "device_alert_states"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(64), nullable=False, index=True)
    zone_id = Column(String(64), nullable=False, index=True)
    severity = Column(Integer, nullable=False)
    last_alerted_at = Column(DateTime(timezone=True), default=get_utc_now)
    is_active = Column(Boolean, default=True)

class WeatherCellCache(Base):
    """Grid-level cache for Open-Meteo forecast queries"""
    __tablename__ = "weather_cell_cache"

    cell_id = Column(String(32), primary_key=True)  # e.g., "13.10_80.30"
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    last_fetched_at = Column(DateTime(timezone=True), default=get_utc_now)
    raw_response = Column(Text, nullable=True)  # Cached JSON string
    is_stale = Column(Boolean, default=False)

class CrowdReport(Base):
    """User-submitted crowd incident report"""
    __tablename__ = "crowd_reports"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(64), nullable=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    report_type = Column(String(32), nullable=False)  # FLOODED_ROAD, BLOCKED_BRIDGE, FALLEN_TREE, OTHER
    description = Column(Text, nullable=True)
    upvotes = Column(Integer, default=0)
    status = Column(String(20), default="PENDING")  # PENDING, APPROVED, REJECTED
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

class SOSLog(Base):
    """SOS activation log"""
    __tablename__ = "sos_logs"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(64), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    prefilled_message = Column(Text, nullable=True)
    emergency_numbers = Column(Text, nullable=True)

# Database Engine & Session
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
