# ClearPath · San Diego

**Mobile-first, community-powered accessible pedestrian routing.** Built with React, Vite, Tailwind CSS, Leaflet, Python, FastAPI, pandas, scikit-learn and Gemini.

> **What it does:** See real San Diego Get It Done service requests on a map; select wheelchair, cane/walker, crutches, low-vision, or standard walking; choose a destination; request a pedestrian route; see reported concerns near that route; optionally request a precautionary alternate route; and submit a photo or written observation. ClearPath is **not** a verified accessible-route or emergency-navigation service.

## Start in development (Windows PowerShell)

Open two terminals **in this project's root folder**:

**Terminal 1 — FastAPI backend:**

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env to set GEMINI_API_KEY and ORS_API_KEY (optional for campus-only demo)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — React frontend:**

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. For phone testing, use a deployed **HTTPS** URL; browser GPS normally won't work on an ordinary HTTP LAN IP.

Check the backend: **http://localhost:8000/api/health** and the automatic API documentation at **http://localhost:8000/docs**.

**What works without API keys:** map, 3,316 preprocessed Get It Done service requests, viewport filtering, mobility profiles, GIS clusters, campus demo lines, community submissions, photo storage, and feedback. Real pedestrian routes require `ORS_API_KEY`; Gemini photo analysis and optional explanations require `GEMINI_API_KEY`.

## Production: one URL for phone installation

Dockerfile builds React and hosts it through FastAPI at the same HTTPS origin, avoiding cross-origin API issues. Deploy using a Docker-supporting service (Render, Railway, Fly.io, etc.) with environment variables `GEMINI_API_KEY` and `ORS_API_KEY`. Start with `docker build -t clearpath .` then `docker run --env-file backend/.env -p 8000:8000 clearpath`. Open the resulting HTTPS URL on a phone and choose **Add to Home Screen** to use its installable web-app interface.

If you deploy the frontend separately (Vercel/Netlify), set `VITE_API_URL` to your **HTTPS** FastAPI host before building and `CORS_ORIGINS` to the exact frontend origin; otherwise same-origin Docker hosting is simpler. Do **not** put Gemini/ORS API keys in `VITE_` environment variables.

## Important notes on routing

- **Actual pedestrian route geometry** comes from OpenRouteService's walking and wheelchair profiles. The route engine inspects City and community reports near the initial path and can request a detour around small avoidance polygons. It uses the detour only if fewer relevant reports lie near it. These are *precautionary suggestions*, not verified closures or ADA certifications.
- City Get It Done data is from **real citizen-submitted service requests**, not confirmed hazards. Category/profile tags are **heuristic possibilities**, not field assessments. Reports may be stale, inaccurate, or unrelated to an actual footpath. We intentionally do not promote them to confirmed blocked routes.
- **Campus demo mode** uses previously sketched, **unverified** Library Walk route candidates from the original Streamlit prototype. These lines are for demonstrating the interface, not navigation.
- Live location uses the phone browser's `navigator.geolocation.watchPosition` with permission; it's not stored by the app until the user explicitly submits a report at a chosen location. Users can choose map pins and manually initiate tracking.
- Community submissions are **unverified**; if Gemini is configured and a photo is provided, it supplies a structured assessment, but cannot measure slopes, certify ADA compliance, or verify elevator operating status merely from a photo.
- Do **not** report crimes or emergencies through ClearPath; use the appropriate official/emergency channels. Avoid other people's personal information and recognizable faces in submitted images.

## Data sources and reuse

`backend/data/city_reports.json` contains **3,316 compact records** extracted from the City of San Diego's publicly available **Get It Done open-request CSV** provided with the hackathon work. Fields include request ID, category, timestamp/status and geographic coordinates, while raw public descriptions and addresses are deliberately excluded for privacy. Attribution: [San Diego Open Data — Get It Done Reports](https://data.sandiego.gov/datasets/get-it-done-reports/).

To regenerate from the full CSV:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/import_city.py ..\get_it_done_requests_open_datasd.csv
```

The large raw city CSV is *not* needed to run the app and is deliberately not bundled. Frontend uses `/api/reports`, not the previous Streamlit `reports.json` format. The old Streamlit code is archived under `legacy_streamlit/` for reference.

## Project structure

```text
ClearPath/
├── frontend/
│   ├── src/App.jsx                 # Mobile navigation & report forms
│   ├── src/styles.css              # Tailwind v4 + refined responsive UI
│   ├── src/components/MapCanvas.jsx # Leaflet map
│   ├── src/hooks/useLiveLocation.js # GPS watch with permission
│   └── public/                     # PWA manifest and icons
├── backend/
│   ├── app/main.py                 # FastAPI routes + production SPA hosting
│   ├── app/routing.py              # OpenRouteService + GIS hazard reroute
│   ├── app/analysis.py             # Gemini photo reasoning
│   ├── app/storage.py              # JSON/photo persistence
│   ├── app/city.py                 # City/community data filters
│   ├── data/city_reports.json      # 3,316 compact service requests
│   └── scripts/import_city.py      # pandas CSV importer
├── legacy_streamlit/             # Original hackathon implementation
└── Dockerfile
```

## What is (and isn't) live

- Live: **GPS position**, **new community submissions on the current server**, and **routing API responses** when a routing key is configured.
- Not live: City's Get It Done CSV is a **snapshot** bundled with this release; reimport to refresh. Community reports/photos saved to server files are **ephemeral on many cloud hosts** and may vanish when the container restarts. For real-world use, move them to managed persistent storage, add abuse moderation, update and verification mechanisms, and expand coverage/data partnerships.

## Test

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

## 📊 Pitch deck
**[Open our presentation slides](https://claude.ai/artifact/VS7a5QXMRxDMLrevpjWRD7)**

Before demoing, test one GPS permission, one destination search, one demo route, one photo/text report, and one real route with your ORS key. Always verify any route on site; do not claim it is safe for a particular user.
