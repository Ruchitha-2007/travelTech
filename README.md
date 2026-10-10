# TravelTech - Crisis Safety & Route Navigation

**TravelTech** is a standalone, real-time crisis safety and navigation platform designed for travelers and citizens during extreme weather and disaster hazards (cyclones, storms, floods, heatwaves).

---

## 📱 Features

1. **Current Location Safety Radar**
   - Live weather metrics (Temperature, Wind Gusts, Precipitation).
   - Real-time hazard monitoring with time horizon filtering (**Today**, **1 Week**, **2 Weeks**, up to **5 Weeks**).
   - Strict active-only hazard filtering (all past and completed events removed).

2. **Destination Route & Highway Navigation**
   - Precise destination address geocoding (street, landmark, locality, pincode).
   - Safe road routing via OSRM geometries with hazard avoidance.
   - Real-time distance and driving duration metrics.

3. **Safe Shelters Finder**
   - Dynamic nearby disaster relief shelters based on live GPS position.
   - Verified inland locations (strictly on land, never in sea/ocean).
   - One-tap emergency call and route navigation to the nearest operational shelter.

4. **Emergency Buzzer & Offline Proximity Alarms**
   - Immediate audio and visual buzzer alarm when approaching hazard zones.
   - Background GPS location monitoring.

5. **Multilingual Support**
   - Native support for 14 languages: English, Tamil, Hindi, Telugu, Kannada, Malayalam, Marathi, Bengali, Spanish, French, German, Japanese, Chinese, and Arabic.

---

## 🚀 Standalone Android APK

The pre-built standalone APK is ready for installation:
- **Download APK**: [`TravelTech.apk`](./TravelTech.apk)
- **Zero Backend Required**: Runs self-contained with offline caching and direct client-side open APIs.

---

## 💻 Tech Stack
- **Android**: Java / Kotlin, Android WebView, Leaflet OpenStreetMap
- **Web**: Vanilla JS, Leaflet.js, Open-Meteo Meteorology APIs, OpenStreetMap Nominatim Geocoding, Project OSRM Routing
- **Backend (Optional)**: FastAPI, SQLite, GDACS Disaster Ingestion
