# hack-for-humanity-hackathon
Beginner Friendly Hackathon hosted by the AI Collective at University of California San Diego. The challenge is to build something with meaningful impact to San Diego in one day.


# ClearPath frontend — quick start

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The workspace had no starter app. This is a standalone frontend with team hooks.
No API key is required to display the map. Map tiles require internet access.

## Handoff

- Backend: write the agreed list of report objects to `reports.json`, photos to
  `photos/`. Use atomic replacement when saving JSON. Refresh reloads the file.
  Non-obstacle reports do not appear. Local photo paths are relative to this folder.
- AI lead: create `ai.py` with `pick_route(routes, reports, profile)` returning
  `{"route_id": "west", "explanation": "..."}`. Valid IDs: `direct`, `west`.
  Called only on button press.
  `routes` contains the route id, name, points, verified flag, and `nearby_reports`.
  These nearby reports have already been filtered for the selected profile.
  Profiles are `wheelchair` (Wheelchair) and `walking_aid` (Walker / crutches / cane).
  Reports use `"affects": {"wheelchair": true, "walking_aid": false}`.
  The frontend filters those flags directly; it does not reclassify photos.
  Wheelchair route guidance: prefer flat, wide, step-free paths, even if longer.
  Walking-aid route guidance: prefer the shortest safe path; narrow paths alone
  need not exclude it. Consider railings, uneven pavement, slopes, and slippery surfaces.
  Return `{"route_id": null, "explanation": "..."}` if none can be recommended.
  Handle all candidates being blocked; do not describe any unverified path as safe.
  The UI validates the returned ID and hides old recommendations after data/profile changes.
- Photo/report form: use `st.session_state.get("report_location")` for the last
  map click (`[lat, lng]`). The frontend also displays copyable coordinates.
- Route geometry: `routes.py` now contains two connected OpenStreetMap candidates
  from north Library Walk to Geisel's south exterior approach: West inner path
  (~248 m) and West outer path (~352 m). They share the initial Library Walk
  approach, then diverge west of Geisel. Intermediate vertices come from mapped
  paths, not straight-line sketches. Source way/node IDs are in `route_sources.json`.
  No included segments are tagged as steps, but missing tags do not prove access.
  Confirm paths, width, slope, and current conditions on site before navigation.
  `verified` remains false. Downloaded 2026-11-07; OpenStreetMap contributors, ODbL.
  https://www.openstreetmap.org/copyright
- Photo classification must not infer exact slope/width or a broken elevator
  solely from appearance. Use unknowns and confirmation as needed.

## Coordinates and campus references

- Geisel building reference: https://ezid.cdlib.org/id/doi:10.34946/D6V01X
- Library Walk location/context: https://calendar.ucsd.edu/library-walk
- Campus map: https://campusmap.ucsd.edu/

Building locations do not establish accessible entrances or path geometry.

## Five-minute demo check

1. Load your team's real reports and photos.
2. Switch Wheelchair / Walker / crutches / cane; confirm the expected pins and counts change.
   For the narrow-path demo, use a report with wheelchair=true, walking_aid=false.
3. Click a pin; verify severity, explanation, timestamp, and photo.
4. Preview each route; check the highlighted line and nearby report counts.
5. Connect the AI hook and press Ask Gemini to compare.
6. Click the map and copy the coordinates into your reporting workflow.

Streamlit Community Cloud: select this repository, `app.py`, and install from
`requirements.txt`. The backend lead should handle durable persistence; local
files on the hosted app are not a durable database.


## Google Maps and more destinations

The sidebar supports nine campus locations and typed addresses. The Google Maps
link works without an API key. The two stored OpenStreetMap routes remain available
for Library Walk / Geisel; other journeys require Google Routes for in-app comparison.

For in-app Google routing and display, enable billing and these APIs in your team's
Google Cloud project. Put keys in `.streamlit/secrets.toml` (gitignored) or Cloud secrets:

```toml
GOOGLE_MAPS_API_KEY = "your-server-key-for-Routes-API"
GOOGLE_MAPS_BROWSER_KEY = "your-browser-key-for-Maps-JavaScript-API"
```

Restrict the server key to Routes API and the browser key to Maps JavaScript API
and your permitted localhost / deployed website referrers. The browser key is
intentionally sent to the browser; never use your Gemini key for this.

Click **Find Google walking routes** to request routes. Results stay in session
until endpoints change; they are not written to disk. Google may return only one
route. Gemini compares actual returned geometry against profile-specific reports;
it cannot guarantee obstacle avoidance or wheelchair access. Google walking routes
may be missing sidewalks/pedestrian paths. Unknown slopes and widths remain unknown.
Google route geometry is displayed only on the Google map; the OpenStreetMap
community map remains available for reporting locations.

Setup: https://developers.google.com/maps/documentation/javascript/get-api-key
Routing: https://developers.google.com/maps/documentation/routes/compute_route_directions
