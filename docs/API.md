# TravelTech API Reference

All requests and responses use JSON. Automatic Swagger documentation is available at `/docs`.

---

## Safety & Location Endpoints

### 1. `POST /api/location/update`
Snaps GPS coordinate to 3x3 neighborhood grid cells, refreshes weather cache if older than 10 mins, performs active-only safety evaluation, and handles deduplication.

**Request:**
```json
{
  "device_id": "phone_uuid_123",
  "lat": 13.0827,
  "lon": 80.2707
}
```

**Response:**
```json
{
  "status": "DANGEROUS",
  "lat": 13.0827,
  "lon": 80.2707,
  "zones": [...],
  "new_alerts": [...],
  "all_clear": null,
  "is_stale": false,
  "checked_at": "2026-10-10T02:00:00Z"
}
```

---

### 2. `POST /api/safety/check`
Checks point safety (e.g., searched destination) after refreshing its 3x3 cell neighborhood.

**Request:**
```json
{
  "lat": 13.0500,
  "lon": 80.2824
}
```

---

### 3. `POST /api/route/safe`
Densifies route points every 200m, performs arrival-time weather sampling, and checks against active hazard zones.

**Request:**
```json
{
  "origin": [13.0827, 80.2707],
  "destination": [12.9941, 80.1709],
  "profile": "driving-car"
}
```

**Statuses:** `SAFE`, `REROUTED`, `UNREACHABLE`, `ORIGIN_UNSAFE`, `DESTINATION_UNSAFE`.

---

### 4. `POST /api/sos`
Logs an SOS trigger and returns formatted text for emergency SMS and official helpline numbers.
