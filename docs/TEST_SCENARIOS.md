# TravelTech Test & Demo Scenarios

Run `python seed_demo.py` in `/backend` to populate the database with Chennai crisis scenarios.

---

## Scenario A: User Inside Flash Flood (Feature 1)
- **Coordinates:** `13.0827, 80.2707` (Chennai Central)
- **Expected Outcome:**
  - Status: `DANGEROUS` (Severity 3).
  - Triggers a full-screen alert on the Android app with alarm sound and vibration.
  - Successive updates at this location send **0 duplicate alerts**.
  - Moving >5 km away to `13.4, 80.1` triggers an **ALL CLEAR** message.

---

## Scenario B: Destination Unsafe Warning (Feature 2)
- **Destination:** `13.0500, 80.2824` (Chennai Marina Beach)
- **Expected Outcome:**
  - Status: `DANGEROUS` (Severity 4 Cyclone).
  - Displays red warning banner and confirmation gate dialog before allowing navigation.

---

## Scenario C: Obstacle on Route Midpoint (Feature 3)
- **Origin:** `13.0827, 80.2707`
- **Destination:** `12.9941, 80.1709`
- **Hazard:** Flood zone situated at Guindy (`13.0067, 80.2025`).
- **Expected Outcome:**
  - Status: `REROUTED` (with detour avoiding the hazard circle) or `UNREACHABLE` if no detours exist.

---

## Scenario D: Expired Hazards (Active-Only Rule)
- Expired hazard at `13.0400, 80.2500` is completely excluded from safety checks and nearby hazard queries.
