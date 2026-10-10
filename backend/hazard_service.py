import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session
from models import HazardZone, WeatherCellCache, Device
from config import CELL_CACHE_TTL_MINUTES, STALE_THRESHOLD_MINUTES, MONITORED_CITIES
from weather_engine import (
    snap_to_grid, get_neighborhood_cells, fetch_open_meteo_batch, parse_cell_hazards
)
from gdacs_ingest import fetch_and_parse_gdacs

logger = logging.getLogger(__name__)

def refresh_cells_if_needed(db: Session, cells: List[Tuple[float, float, str]], force: bool = False, now_utc: Optional[datetime] = None) -> Tuple[List[str], bool]:
    """
    Checks cell cache TTL (10 minutes). For any cells older than 10 mins (or missing),
    performs batched Open-Meteo call, updates cache, and synchronizes HazardZones.
    Returns (refreshed_cell_ids, is_stale_fallback_used).
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    cells_to_fetch = []
    stale_used = False

    for c_lat, c_lon, cell_id in cells:
        cached = db.query(WeatherCellCache).filter(WeatherCellCache.cell_id == cell_id).first()
        needs_fetch = False
        if force or not cached or not cached.last_fetched_at:
            needs_fetch = True
        else:
            last_fetch = cached.last_fetched_at
            if last_fetch.tzinfo is None:
                last_fetch = last_fetch.replace(tzinfo=timezone.utc)
            if (now_utc - last_fetch).total_seconds() > CELL_CACHE_TTL_MINUTES * 60:
                needs_fetch = True

        if needs_fetch:
            cells_to_fetch.append((c_lat, c_lon, cell_id))

    if not cells_to_fetch:
        return [], False

    # Perform batched fetch
    batch_results = fetch_open_meteo_batch(cells_to_fetch)
    refreshed_ids = []

    for c_lat, c_lon, cell_id in cells_to_fetch:
        forecast_data = batch_results.get(cell_id)
        cached = db.query(WeatherCellCache).filter(WeatherCellCache.cell_id == cell_id).first()

        if forecast_data:
            # Update cache
            if not cached:
                cached = WeatherCellCache(
                    cell_id=cell_id, lat=c_lat, lon=c_lon,
                    last_fetched_at=now_utc, raw_response="", is_stale=False
                )
                db.add(cached)
            else:
                cached.last_fetched_at = now_utc
                cached.is_stale = False

            # Delete old Open-Meteo hazard zones for this cell (replace, don't duplicate)
            db.query(HazardZone).filter(HazardZone.cell_id == cell_id).delete()

            # Parse new hazards and add
            new_hazards = parse_cell_hazards(c_lat, c_lon, cell_id, forecast_data, now_utc)
            for nh in new_hazards:
                hz = HazardZone(**nh)
                db.add(hz)
            refreshed_ids.append(cell_id)
        else:
            # Fallback to stale data if available
            if cached:
                last_fetch = cached.last_fetched_at
                if last_fetch and last_fetch.tzinfo is None:
                    last_fetch = last_fetch.replace(tzinfo=timezone.utc)
                age_mins = (now_utc - last_fetch).total_seconds() / 60.0 if last_fetch else 999
                if age_mins > STALE_THRESHOLD_MINUTES:
                    cached.is_stale = True
                    stale_used = True
            logger.warning(f"Open-Meteo call failed or returned empty for cell {cell_id}.")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving refreshed weather cells to DB: {e}")

    return refreshed_ids, stale_used

def sync_gdacs_events(db: Session, now_utc: Optional[datetime] = None) -> int:
    """Fetches GDACS events and syncs active/upcoming events to database."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    zones = fetch_and_parse_gdacs(now_utc)
    count = 0
    for z in zones:
        existing = db.query(HazardZone).filter(HazardZone.id == z["id"]).first()
        if existing:
            existing.severity = z["severity"]
            existing.end_time = z["end_time"]
            existing.radius_km = z["radius_km"]
        else:
            db.add(HazardZone(**z))
            count += 1
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error syncing GDACS: {e}")
    return count

def cleanup_expired_zones(db: Session, now_utc: Optional[datetime] = None) -> int:
    """Deletes expired hazard zones where end_time < now_utc."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    deleted_count = db.query(HazardZone).filter(HazardZone.end_time < now_utc).delete()
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error during cleanup: {e}")
    return deleted_count

def run_background_sync(db: Session):
    """Background task running every 10 minutes: sync GDACS + monitored cities + active devices."""
    now_utc = datetime.now(timezone.utc)
    logger.info(f"Running background sync at {now_utc.isoformat()}...")
    
    # 1. Clean expired zones
    cleanup_expired_zones(db, now_utc)

    # 2. Sync GDACS
    sync_gdacs_events(db, now_utc)

    # 3. Collect cells from monitored cities
    target_cells = set()
    for city in MONITORED_CITIES:
        _, _, cell_id = snap_to_grid(city["lat"], city["lon"])
        target_cells.add((city["lat"], city["lon"], cell_id))

    # 4. Collect cells from devices active in last 24h
    cutoff_24h = now_utc - timedelta(hours=24)
    active_devices = db.query(Device).filter(Device.last_seen >= cutoff_24h).all()
    for dev in active_devices:
        if dev.last_lat is not None and dev.last_lon is not None:
            _, _, cell_id = snap_to_grid(dev.last_lat, dev.last_lon)
            target_cells.add((dev.last_lat, dev.last_lon, cell_id))

    # 5. Batch refresh collected cells
    refresh_cells_if_needed(db, list(target_cells), force=False, now_utc=now_utc)
    logger.info("Background sync completed.")
