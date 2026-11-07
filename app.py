"""ClearPath frontend. Run: streamlit run app.py"""
import json
import math
from pathlib import Path

import streamlit as st
from streamlit_folium import st_folium

from map_ui import build_map, local_photo, relevant_reports, route_context
from routes import ROUTES, START_NAME, END_NAME

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="ClearPath · UCSD", page_icon="📍", layout="wide")


def load_reports():
    path = ROOT / "reports.json"
    if not path.exists():
        return []
    try:
        records = json.loads(path.read_text())
        if not isinstance(records, list):
            raise ValueError("Expected a JSON list")
        valid = []
        for record in records:
            if not isinstance(record, dict):
                continue
            try:
                lat, lng = float(record["lat"]), float(record["lng"])
                if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
                    continue
                if not isinstance(record.get("affects", {}), dict):
                    continue
                valid.append({**record, "lat": lat, "lng": lng})
            except (KeyError, ValueError, TypeError):
                continue
        if len(valid) != len(records):
            st.warning("Some report records have invalid coordinates or fields and were skipped.")
        return valid
    except (OSError, ValueError) as exc:
        st.error(f"Could not load reports.json: {exc}")
        return []


st.title("ClearPath")
st.markdown("### Campus paths change. Your map should too.")
st.caption("UC San Diego · Photo-backed community obstacle reports")

with st.sidebar:
    st.header("Plan your path")
    profile = st.radio("Mobility profile", ["wheelchair", "walking_aid"],
                       format_func=lambda p: {"wheelchair": "Wheelchair", "walking_aid": "Walker / crutches / cane"}[p])
    st.text_input("From", START_NAME, disabled=True)
    st.text_input("To", END_NAME, disabled=True)
    st.button("Refresh reports", use_container_width=True)
    show_all = st.checkbox("Show reports for both profiles", value=False)
    st.divider()
    st.markdown("🔴 **Impassable** · 🟠 **Difficult** · 🟢 **Minor**")
    st.caption("Severity and affected profiles are report assessments, not verified measurements.")

reports = load_reports()
visible = [r for r in reports if r.get("is_obstacle") is True] if show_all else relevant_reports(reports, profile)
contexts = route_context(ROUTES, reports, profile)
st.warning("Prototype: routes follow OpenStreetMap path geometry. Accessibility and current conditions have not been checked on site.")

map_col, info_col = st.columns([2.2, 1], gap="large")
with info_col:
    st.subheader("Route comparison")
    selected_id = st.selectbox("Preview a candidate", [r["id"] for r in ROUTES],
                               format_func=lambda rid: next(r["name"] for r in ROUTES if r["id"] == rid),
                               on_change=lambda: st.session_state.pop("recommendation", None))
    for candidate in contexts:
        nearby = candidate["nearby_reports"]
        blocked = sum(r.get("severity") == "impassable" for r in nearby)
        st.markdown(f'**{candidate["name"]}** · about {candidate["distance_m"]} m — {len(nearby)} nearby reports' + (f" · {blocked} impassable" if blocked else ""))
    st.caption("Nearby = within 15 m of a candidate line; proximity does not prove a path is blocked. No reports does not mean a path is clear.")
    if st.button("Ask Gemini to compare", type="primary", use_container_width=True):
        try:
            from ai import pick_route
        except ImportError:
            st.info("AI hook ready: add ai.pick_route(routes, reports, profile). See README.md.")
        else:
            try:
                with st.spinner("Comparing reported obstacles…"):
                    result = pick_route(contexts, reports, profile)
                if not isinstance(result, dict) or "route_id" not in result or result.get("route_id") not in {None, *(r["id"] for r in ROUTES)} or not isinstance(result.get("explanation"), str):
                    raise ValueError("Expected route_id and explanation")
                st.session_state["recommendation"] = {"profile": profile, "reports": reports, "result": result}
            except Exception as exc:
                st.error(f"Route comparison unavailable: {exc}")
    saved = st.session_state.get("recommendation")
    if saved and saved["profile"] == profile and saved["reports"] == reports:
        result = saved["result"]
        selected_id = result["route_id"]
        if selected_id is None:
            st.warning("Gemini could not recommend a candidate from the available evidence.")
        else:
            st.info(f'Gemini suggests: {next(r["name"] for r in ROUTES if r["id"] == selected_id)}')
        st.write(result["explanation"])
    st.metric("Reports shown", len(visible))

with map_col:
    map_result = st_folium(build_map(visible, ROUTES, selected_id,
                          st.session_state.get("report_location")),
                          height=580, use_container_width=True,
                          returned_objects=["last_clicked"], key="campus_map")
    clicked = (map_result or {}).get("last_clicked")
    if clicked:
        st.session_state["report_location"] = [clicked["lat"], clicked["lng"]]
    location = st.session_state.get("report_location")
    st.caption("Click the map to select a location for the report team.")
    if location:
        st.code(json.dumps({"lat": round(location[0], 6), "lng": round(location[1], 6)}), language="json")

st.subheader("Obstacle reports")
if not visible:
    st.info("No obstacle reports to show for this profile. Add reports.json or switch profiles.")
for report in visible:
    title = f'{report.get("severity", "unknown").upper()} · {report.get("type", "other").replace("_", " ").title()} · {report.get("id", "")}'
    with st.expander(title):
        st.write(report.get("explanation", "No explanation supplied."))
        st.caption(f'Reported {report.get("reported_at", "unknown")} · {report["lat"]:.6f}, {report["lng"]:.6f}')
        photo = local_photo(report.get("photo_url", ""))
        if photo:
            try:
                st.image(str(photo), width=360)
            except Exception:
                st.caption("Photo unavailable.")
