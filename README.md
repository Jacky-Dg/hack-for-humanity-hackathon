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
  `{"route_id": "west", "explanation": "..."}`. Called only on button press.
  `routes` contains the route id, name, points, verified flag, and `nearby_reports`.
  These nearby reports have already been filtered for the selected profile.
  Return `{"route_id": null, "explanation": "..."}` if none can be recommended.
  Handle all candidates being blocked; do not describe any unverified path as safe.
  The UI validates the returned ID and hides old recommendations after data/profile changes.
- Photo/report form: use `st.session_state.get("report_location")` for the last
  map click (`[lat, lng]`). The frontend also displays copyable coordinates.
- Route geometry: edit `routes.py`. All three are illustrative sketches around
  Library Walk, NOT verified campus routes. Confirm endpoints, walk the paths,
  replace intermediate vertices, and then update verification labels in the UI.
  No stair, slope, or clearance measurements have been established.
- Photo classification must not infer exact slope/width or a broken elevator
  solely from appearance. Use unknowns and confirmation as needed.

## Coordinates and campus references

- Geisel building reference: https://ezid.cdlib.org/id/doi:10.34946/D6V01X
- Library Walk location/context: https://calendar.ucsd.edu/library-walk
- Campus map: https://maps.ucsd.edu/

Building locations do not establish accessible entrances or path geometry.

## Five-minute demo check

1. Load your team's real reports and photos.
2. Switch wheelchair / low vision; confirm the expected pins and counts change.
3. Click a pin; verify severity, explanation, timestamp, and photo.
4. Preview each route; check the highlighted line and nearby report counts.
5. Connect the AI hook and press Ask Gemini to compare.
6. Click the map and copy the coordinates into your reporting workflow.

Streamlit Community Cloud: select this repository, `app.py`, and install from
`requirements.txt`. The backend lead should handle durable persistence; local
files on the hosted app are not a durable database.
