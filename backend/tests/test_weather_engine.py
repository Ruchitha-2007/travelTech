import pytest
from datetime import datetime, timezone, timedelta
from weather_engine import snap_to_grid, get_neighborhood_cells, parse_cell_hazards

def test_snap_to_grid():
    # User in Chennai: 13.0827, 80.2707
    c_lat, c_lon, cell_id = snap_to_grid(13.0827, 80.2707, 0.1)
    assert c_lat == 13.1
    assert c_lon == 80.3
    assert cell_id == "13.10_80.30"

def test_get_neighborhood_cells():
    cells = get_neighborhood_cells(13.0827, 80.2707, 0.1)
    assert len(cells) == 9
    cell_ids = [c[2] for c in cells]
    assert "13.10_80.30" in cell_ids
    assert "13.20_80.30" in cell_ids  # North
    assert "13.00_80.30" in cell_ids  # South
    assert "13.10_80.40" in cell_ids  # East
    assert "13.10_80.20" in cell_ids  # West

def test_parse_cell_hazards_hourly_and_past_hour_filtering():
    now_utc = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    
    # Mock Open-Meteo forecast data with past, current, and upcoming hours
    mock_forecast = {
        "hourly": {
            "time": [
                "2026-10-10T10:00",  # Past: 100mm rain (MUST BE IGNORED)
                "2026-10-10T11:00",  # Past: 80km/h wind (MUST BE IGNORED)
                "2026-10-10T12:00",  # Current: 35mm rain -> Severity 3 (DANGEROUS)
                "2026-10-10T13:00",  # Upcoming: 55mm rain -> Severity 4 (EXTREME)
                "2026-10-10T14:00",  # Upcoming: calm (0mm)
            ],
            "precipitation": [100.0, 5.0, 35.0, 55.0, 0.0],
            "wind_gusts_10m": [10.0, 80.0, 20.0, 25.0, 10.0],
            "temperature_2m": [30.0, 30.0, 32.0, 32.0, 31.0],
            "weather_code": [0, 0, 80, 80, 0]
        }
    }

    hazards = parse_cell_hazards(13.1, 80.3, "13.10_80.30", mock_forecast, now_utc)
    
    # Past hour high wind (11:00) must NOT create any HIGH_WIND hazard
    wind_hazards = [h for h in hazards if h["type"] == "HIGH_WIND"]
    assert len(wind_hazards) == 0

    # Rain hazard must be created with max severity 4 (from 13:00)
    rain_hazards = [h for h in hazards if h["type"] == "HEAVY_RAIN"]
    assert len(rain_hazards) == 1
    rain_hz = rain_hazards[0]
    assert rain_hz["severity"] == 4
    assert rain_hz["verified"] is False
    assert "Open-Meteo forecast" in rain_hz["source"]
    assert rain_hz["start_time"] == datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)

def test_remote_location_without_monitored_cities():
    # Coastal village in Odisha: 19.8135, 85.8312 (Puri coast)
    c_lat, c_lon, cell_id = snap_to_grid(19.8135, 85.8312, 0.1)
    assert c_lat == 19.8
    assert c_lon == 85.8
    assert cell_id == "19.80_85.80"
    
    # Neighborhood generates 9 cells correctly anywhere in the world
    neighbors = get_neighborhood_cells(19.8135, 85.8312, 0.1)
    assert len(neighbors) == 9
