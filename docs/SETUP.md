# TravelTech Setup Guide

## 1. Backend Setup

### Prerequisites
- Python 3.11+
- Virtual environment (optional but recommended)

### Steps
1. Navigate to `/backend`:
   ```bash
   cd backend
   ```
2. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
   *(Optional: Add your free OpenRouteService key as `ORS_API_KEY=...` to test live ORS directions.)*
4. Seed demo scenarios:
   ```bash
   python seed_demo.py
   ```
5. Run the server:
   ```bash
   python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
   - Interactive docs: `http://localhost:8000/docs`
   - Web Dashboard: `http://localhost:8000/web`

---

## 2. Android App Setup

### Prerequisites
- Android Studio Iguana / Jellyfish or later
- JDK 17
- Android SDK 34 (minSdk 26)

### Steps
1. Open `/android` in Android Studio.
2. Let Gradle sync dependencies.
3. Run on an Android Emulator:
   - The default base URL `http://10.0.2.2:8000` automatically targets your host PC.
4. Run on a Real Device via Wi-Fi:
   - Ensure the phone and PC are on the same Wi-Fi.
   - Update `BASE_URL` in `app/build.gradle.kts` to your PC's local IP (e.g., `http://192.168.1.5:8000`).
