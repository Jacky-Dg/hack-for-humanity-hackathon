"""ClearPath frontend. Run: streamlit run app.py"""
import json
import math
from pathlib import Path

import streamlit as st
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation

from backend import save_report

from map_ui import build_map, local_photo, relevant_reports, route_context
from routes import ROUTES, START_NAME, END_NAME
from google_maps_ui import setting, fetch_routes, render_google_map, directions_url

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

# ==========================================
# AUTOMATIC GPS LOCATION
# ==========================================

if "report_location" not in st.session_state:
    st.session_state["report_location"] = None

if "gps_request" not in st.session_state:
    st.session_state["gps_request"] = 0

# Allow the user to refresh their location
if st.button("📍 Refresh GPS Location"):
    st.session_state["gps_request"] += 1
    st.session_state["use_new_gps"] = True

# Ask browser for location permission
gps_key = f"clearpath_gps_{st.session_state['gps_request']}"

location = get_geolocation(component_key=gps_key)

if location and "coords" in location:

    coords = location["coords"]

    latitude = coords["latitude"]
    longitude = coords["longitude"]

    # Only process each location request once
    if st.session_state.get("last_gps_key") != gps_key:

        st.session_state["gps_location"] = {
            "lat": latitude,
            "lng": longitude,
            "accuracy": coords.get("accuracy")
        }

        # Initialize report location from GPS.
        # Preserve manually selected map locations,
        # unless the user explicitly refreshes GPS.
        if (
            st.session_state["report_location"] is None
            or st.session_state.get("use_new_gps", False)
        ):
            st.session_state["report_location"] = [
                latitude,
                longitude
            ]

        st.session_state["last_gps_key"] = gps_key
        st.session_state["use_new_gps"] = False

    st.success("📍 GPS location detected!")

    accuracy = coords.get("accuracy")

    if accuracy is not None:
        st.caption(f"Location accuracy: ±{accuracy:.0f} meters")

        if accuracy > 30:
            st.warning(
                "GPS accuracy is limited. "
                "Please verify the obstacle location on the map."
            )

elif location and "error" in location:

    st.warning(
        "GPS unavailable. You can still select "
        "the obstacle location manually on the map."
    )

else:
    st.info("Waiting for GPS location...")

def change_endpoint(changed):
    other = "destination" if changed == "origin" else "origin"
    if st.session_state.get(other) == st.session_state[changed]:
        st.session_state[other] = END_NAME if st.session_state[changed] == START_NAME else START_NAME
    st.session_state.pop("recommendation", None)


CAMPUS_LOCATIONS = [START_NAME, END_NAME, "Price Center, UC San Diego",
                    "RIMAC, UC San Diego", "Warren Mall, UC San Diego",
                    "Sixth College, UC San Diego", "UC San Diego Central Campus Station",
                    "WongAvery Library, UC San Diego", "Mandeville Center, UC San Diego"]
route_key = setting("GOOGLE_MAPS_API_KEY")
browser_key = setting("GOOGLE_MAPS_BROWSER_KEY")
st.session_state.setdefault("origin", START_NAME)
st.session_state.setdefault("destination", END_NAME)

with st.sidebar:
    st.header("Plan your path")
    profile = st.radio("Mobility profile", ["wheelchair", "walking_aid"],
                       format_func=lambda p: {"wheelchair": "Wheelchair", "walking_aid": "Walker / crutches / cane"}[p])
    origin = st.selectbox("From", CAMPUS_LOCATIONS, key="origin", accept_new_options=True,
                          on_change=change_endpoint, args=("origin",))
    destination = st.selectbox("To", CAMPUS_LOCATIONS, key="destination", accept_new_options=True,
                               on_change=change_endpoint, args=("destination",))
    st.caption("Choose a campus location or type a specific address.")
    st.link_button("Open walking directions in Google Maps", directions_url(origin, destination))
    if not route_key:
        st.caption("Enable in-app routing with GOOGLE_MAPS_API_KEY (Routes API).")
    if st.button("Find Google walking routes", disabled=not route_key or origin == destination):
        try:
            with st.spinner("Finding walking routes…"):
                result = fetch_routes(origin, destination, route_key)
            st.session_state["google_journey"] = {"journey": (origin, destination), "routes": result}
            st.session_state.pop("recommendation", None)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
        except Exception:
            st.error("Could not reach Google Routes. Check connectivity and API setup.")
    st.button("Refresh reports", use_container_width=True)
    show_all = st.checkbox("Show reports for both profiles", value=False)
    st.divider()
    st.markdown("🔴 **Impassable** · 🟠 **Difficult** · 🟢 **Minor**")
    st.caption("Severity and affected profiles are report assessments, not verified measurements.")

active_routes = [
    {**route,
     "points": list(reversed(route["points"])) if origin == END_NAME else list(route["points"]),
     "start_name": origin, "end_name": destination}
    for route in ROUTES
] if {origin, destination} == {START_NAME, END_NAME} else []
google_journey = st.session_state.get("google_journey")
if google_journey and google_journey["journey"] == (origin, destination):
    active_routes = google_journey["routes"]
journey = (origin, destination)

reports = load_reports()
visible = [r for r in reports if r.get("is_obstacle") is True] if show_all else relevant_reports(reports, profile)
contexts = route_context(active_routes, reports, profile)
if active_routes and active_routes[0].get("source") == "Google Maps":
    st.warning("Google walking routes may be missing sidewalks or pedestrian paths. They are not verified accessible routes. Community reports may also be incomplete.")
else:
    st.caption("Community map: accessibility and current path conditions are unverified.")
if not active_routes:
    st.info("For this journey, open Google Maps using the sidebar link, or configure the API keys and click Find Google walking routes.")

map_col, info_col = st.columns([2.2, 1], gap="large")
with info_col:
    st.subheader("Route comparison")
    selected_id = st.selectbox("Preview route", [r["id"] for r in active_routes],
                               format_func=lambda rid: next(r["name"] for r in active_routes if r["id"] == rid),
                               on_change=lambda: st.session_state.pop("recommendation", None))
    for candidate in contexts:
        nearby = candidate["nearby_reports"]
        blocked = sum(r.get("severity") == "impassable" for r in nearby)
        st.markdown(f'**{candidate["name"]}** · about {candidate["distance_m"]} m — {len(nearby)} nearby reports' + (f" · {blocked} impassable" if blocked else ""))
    st.caption("Nearby = within 15 m of a candidate line; proximity does not prove a path is blocked. No reports does not mean a path is clear.")
    if st.button("Ask Gemini to compare", type="primary", use_container_width=True, disabled=not active_routes):
        try:
            from ai import pick_route
        except ImportError:
            st.info("AI hook ready: add ai.pick_route(routes, reports, profile). See README.md.")
        else:
            try:
                with st.spinner("Comparing reported obstacles…"):
                    result = pick_route(contexts, reports, profile)
                if not isinstance(result, dict) or "route_id" not in result or result.get("route_id") not in {None, *(r["id"] for r in active_routes)} or not isinstance(result.get("explanation"), str):
                    raise ValueError("Expected route_id and explanation")
                st.session_state["recommendation"] = {"profile": profile, "reports": reports, "journey": journey, "result": result}
            except Exception as exc:
                st.error(f"Route comparison unavailable: {exc}")
    saved = st.session_state.get("recommendation")
    if saved and saved["profile"] == profile and saved["reports"] == reports and saved.get("journey") == journey:
        result = saved["result"]
        selected_id = result["route_id"]
        if selected_id is None:
            st.warning("Gemini could not recommend a candidate from the available evidence.")
        else:
            st.info(f'Gemini suggests: {next(r["name"] for r in active_routes if r["id"] == selected_id)}')
        st.write(result["explanation"])
    st.metric("Reports shown", len(visible))

with map_col:
    if active_routes and active_routes[0].get("source") == "Google Maps":
        if browser_key:
            render_google_map(active_routes, visible, selected_id, browser_key)
        else:
            st.info("Add GOOGLE_MAPS_BROWSER_KEY (Maps JavaScript API) to display Google routes here.")
            st.link_button("View directions on Google Maps", directions_url(origin, destination))
        st.caption("Use the community map below to select a report location.")
    community_routes = [r for r in active_routes if r.get("source") != "Google Maps"]
    map_result = st_folium(build_map(visible, community_routes, selected_id,
                          st.session_state.get("report_location")),
                          height=580, use_container_width=True,
                          returned_objects=["last_clicked"], key="campus_map")
    clicked = (map_result or {}).get("last_clicked")

if clicked:
    click_position = (
        clicked["lat"],
        clicked["lng"]
    )

    # Avoid reapplying an old click on every rerun
    if st.session_state.get("last_map_click") != click_position:

        st.session_state["report_location"] = [
            clicked["lat"],
            clicked["lng"]
        ]

        st.session_state["last_map_click"] = click_position
    location = st.session_state.get("report_location")
    st.caption("Click the map to select a location for the report team.")
    if location:
        st.code(json.dumps({"lat": round(location[0], 6), "lng": round(location[1], 6)}), language="json")

# ==========================================
# REPORT AN OBSTACLE
# ==========================================

st.divider()
st.subheader("🚧 Report an Accessibility Obstacle")

st.write(
    "Help make UCSD more accessible by reporting "
    "blocked ramps, broken elevators, construction, "
    "or other obstacles."
)

# STEP 1: Choose photo source
photo_source = st.radio(
    "How would you like to submit your photo?",
    ["Camera", "Upload Photo"],
    horizontal=True
)

if photo_source == "Camera":

    photo = st.camera_input(
        "📸 Take a photo of the obstacle"
    )

else:

    photo = st.file_uploader(
        "Upload an obstacle photo",
        type=["jpg", "jpeg", "png", "webp"]
    )


# STEP 2: Get obstacle location
report_location = st.session_state.get("report_location")

st.markdown("#### 📍 Obstacle Location")

if report_location:

    lat, lng = report_location

    st.success("Location selected!")

    st.write(f"Latitude: {lat:.6f}")
    st.write(f"Longitude: {lng:.6f}")

    st.caption(
        "Please check that this location marks the obstacle. "
        "Tap the map above to correct it."
    )

else:

    st.warning(
        "Location unavailable. Enable GPS or "
        "tap the obstacle location on the map."
    )


# STEP 3: Confirm and submit
confirmed = st.checkbox(
    "I confirm that the selected location is correct."
)

if st.button(
    "Submit Obstacle Report",
    type="primary",
    disabled=(
        photo is None
        or report_location is None
        or not confirmed
    )
):

    try:

        # Import AI functionality
        from ai import analyze_photo

        with st.spinner("Gemini is analyzing your photo..."):

            # STEP 4: Analyze photo using Gemini
            analysis = analyze_photo(
                photo.getvalue()
            )

            # STEP 5: Save report using backend
            report = save_report(
                photo,
                lat,
                lng,
                analysis
            )

        st.success(
            f"✅ Obstacle successfully reported! ID: {report['id']}"
        )

        # STEP 6: Refresh application
        st.rerun()

    except ImportError:

        st.error(
            "Gemini photo analysis is not connected yet. "
            "Ask the AI Lead to implement ai.analyze_photo()."
        )

    except ValueError as e:

        st.warning(str(e))

    except Exception as e:

        st.error(f"Unable to submit report: {e}")

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

from get_it_done_view import show_get_it_done_map

with st.expander("Explore Real San Diego Reports"):
    show_get_it_done_map()
