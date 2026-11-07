# Previous Streamlit proof of concept (archive)

This directory preserves the Streamlit/Gemini/folium prototype files provided during the hackathon. It is **not** used by the new React + FastAPI application. The former campus line routes and demo City Get It Done data are archival references only.

The React application uses `backend/data/city_reports.json` (regenerated from the original San Diego Get It Done CSV), and the fallback campus sketch routes are preserved in `backend/data/legacy_routes.py`.

The original `app.py` referenced an `ai.py` module that was not among the uploaded original files. The new code replaces it with `backend/app/analysis.py` and `backend/app/routing.py`.
