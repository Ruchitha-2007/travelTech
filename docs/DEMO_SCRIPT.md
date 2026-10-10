# TravelTech Live Demo Script

**Total Demo Duration:** 3–5 Minutes

### Step 1: Start the Backend & Open Web Dashboard
1. Terminal:
   ```bash
   cd backend
   python seed_demo.py
   python -m uvicorn main:app --port 8000
   ```
2. Open browser: `http://localhost:8000/web`
3. Point out the color palette: sky-blue ambient canvas, crisp white cards, and clear severity badges.

### Step 2: Demonstrate Feature 1 (Hazardous Location & Dedup)
1. On the map or via API, simulate the tourist at Chennai Central (`13.0827, 80.2707`).
2. Show the `DANGEROUS` status card and alert item.
3. Show that repeated location reports at that coordinate generate no duplicate spam alerts.
4. Move the coordinate out of the zone to demonstrate the instant **ALL CLEAR** notification.

### Step 3: Demonstrate Feature 2 (Destination Warning)
1. In the search box, query Marina Beach (`13.0500, 80.2824`).
2. Point out the red warning badge and the confirmation dialog barrier.

### Step 4: Demonstrate Feature 3 (Route Safety & Detour)
1. Request a route from Central to Airport.
2. Show that the midpoint hazard at Guindy is detected and marked either `REROUTED` or `UNREACHABLE` with the exact message *"Reaching the destination is not possible right now"*.

### Step 5: Demonstrate Multilingual & Emergency SOS
1. Switch language to Tamil or Hindi and show pre-translated templates.
2. Show the SOS button triggering the emergency SMS template and the 112 dialer.
