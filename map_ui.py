"""Map helpers; no Streamlit dependency so they can be reused by the team."""
import base64
import html
import math
from pathlib import Path

COLORS = {"impassable": "#dc2626", "difficult": "#c2410c", "minor": "#15803d"}
ROOT = Path(__file__).resolve().parent


def distance_to_route_m(lat, lng, points):
    """Local point-to-segment distance, not distance to a route's vertices."""
    scale_x = 111320 * math.cos(math.radians(lat))
    def xy(p):
        return ((p[1] - lng) * scale_x, (p[0] - lat) * 111320)
    best = float("inf")
    for a, b in zip(points, points[1:]):
        ax, ay = xy(a)
        bx, by = xy(b)
        dx, dy = bx - ax, by - ay
        length = dx * dx + dy * dy
        t = max(0, min(1, -(ax * dx + ay * dy) / length)) if length else 0
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def relevant_reports(reports, profile):
    return [r for r in reports if r.get("is_obstacle") is True
            and r.get("affects", {}).get(profile) is True]


def route_context(routes, reports, profile):
    relevant = relevant_reports(reports, profile)
    return [{**route, "nearby_reports": [r for r in relevant
             if distance_to_route_m(r["lat"], r["lng"], route["points"]) <= 15]}
            for route in routes]


def local_photo(value):
    # Only serve local photos in this app's photos directory.
    path = (ROOT / str(value)).resolve()
    if not path.is_relative_to(ROOT / "photos") or not path.is_file():
        return None
    return path


def popup_html(report):
    esc = lambda value: html.escape(str(value))
    affects = ", ".join(k.replace("_", " ") for k, v in report.get("affects", {}).items() if v)
    content = (f'<div style="font:16px sans-serif;max-width:290px">'
               f'<b>{esc(report.get("type", "other").replace("_", " ").title())}</b>'
               f'<p><b>{esc(report.get("severity", "unknown").upper())}</b></p>'
               f'<p>{esc(report.get("explanation", "No explanation supplied."))}</p>'
               f'<p>Affects: {esc(affects or "Unspecified")}</p>'
               f'<small>Reported: {esc(report.get("reported_at", "Unknown"))}'
               f' · ID: {esc(report.get("id", ""))}</small>')
    path = local_photo(report.get("photo_url", ""))
    if path and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
        from PIL import Image, ImageOps
        from io import BytesIO
        try:
            with Image.open(path) as original:
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.thumbnail((480, 360))
                buffer = BytesIO()
                image.save(buffer, format="JPEG")
            data = base64.b64encode(buffer.getvalue()).decode()
            content += f'<p><img alt="Reported obstacle" src="data:image/jpeg;base64,{data}" style="width:100%"></p>'
        except (OSError, ValueError):
            content += '<p>Photo unavailable.</p>'
    return content + "</div>"


def build_map(reports, routes, selected_id=None, location=None):
    import folium
    from routes import START, END, START_NAME, END_NAME
    campus = folium.Map(location=[32.8802, -117.2376], zoom_start=18,
                        tiles="OpenStreetMap", control_scale=True)
    for route in routes:
        selected = route["id"] == selected_id
        folium.PolyLine(route["points"], color="#075985" if selected else "#64748b",
                        weight=8 if selected else 4, opacity=1 if selected else .65,
                        dash_array=None if selected else "8 8",
                        tooltip=route["name"] + " — unverified candidate").add_to(campus)
    start = routes[0]["points"][0] if routes else START
    end = routes[0]["points"][-1] if routes else END
    start_name = routes[0].get("start_name", START_NAME) if routes else START_NAME
    end_name = routes[0].get("end_name", END_NAME) if routes else END_NAME
    for point, name, icon in ([(start, start_name, "play"), (end, end_name, "flag")] if routes else []):
        folium.Marker(point, tooltip=name,
                      icon=folium.Icon(color="blue", icon=icon)).add_to(campus)
    for report in reports:
        color = COLORS.get(report.get("severity"), "#64748b")
        folium.CircleMarker([report["lat"], report["lng"]], radius=11,
                            color="white", weight=2, fill=True, fill_color=color,
                            fill_opacity=1,
                            tooltip=f'{report.get("severity", "unknown")} · {report.get("type", "other")}',
                            popup=folium.Popup(popup_html(report), max_width=320)).add_to(campus)
    if location:
        folium.Marker(location, tooltip="Selected report location",
                      icon=folium.Icon(color="purple", icon="camera")).add_to(campus)
    return campus
