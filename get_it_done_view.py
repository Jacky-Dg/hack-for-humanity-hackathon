"""Optional Get It Done demo map for ClearPath (no impact on UCSD route engine)."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

import folium
import streamlit as st
from streamlit_folium import st_folium

from map_ui import COLORS

ROOT = Path(__file__).resolve().parent


def show_get_it_done_map() -> None:
    st.subheader("San Diego Get It Done · Demonstration")
    st.warning(
        "City resident reports (unverified), NOT UCSD campus obstacles. Gemini estimated "
        "each report's impact from the city's category only (no photo), so severity is a "
        "likely impact, not a confirmed one. Likely hazards within 15 m of a route are included when Gemini compares routes."
    )
    path = ROOT / "get_it_done_demo.json"
    if not path.exists():
        st.info("Run `python import_get_it_done.py --download` first.")
        return
    try:
        reports = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        st.error("Unable to read Get It Done demo JSON.")
        return
    if not isinstance(reports, list) or not reports:
        st.info("No Get It Done reports matched your import filters.")
        return
    assessed = [r for r in reports if r.get("assessed_by")]
    hazards = [r for r in assessed if r.get("is_obstacle")]
    st.caption(f"Displaying {len(reports)} imported city service requests. Source: City of San Diego Open Data Portal.")
    if assessed:
        st.caption(f"Gemini estimates {len(hazards)} of {len(assessed)} assessed reports likely affect walking routes. "
                   "🔴 Impassable · 🟠 Difficult · 🟢 Minor · ⚪ Not a walking hazard")
    else:
        st.info("Not assessed by Gemini yet. Run `python assess_city.py`.")
    coords = [(r["lat"], r["lng"]) for r in reports]
    avg_lat = sum(lat for lat, _ in coords) / len(coords)
    avg_lng = sum(lng for _, lng in coords) / len(coords)
    m = folium.Map(location=[avg_lat, avg_lng], zoom_start=13, tiles="OpenStreetMap")
    for r in reports:
        title = escape(str(r.get("source_id", "")))
        category = escape(str(r.get("city_label", "")))
        if r.get("assessed_by"):
            affects = ", ".join(k.replace("_", " ") for k, v in r.get("affects", {}).items() if v) or "neither profile"
            color = COLORS.get(r.get("severity"), "#64748b") if r.get("is_obstacle") else "#94a3b8"
            tooltip = (f'Likely {r.get("severity")} · affects {affects}' if r.get("is_obstacle")
                       else "Likely not a walking hazard")
            body = (f"<b>{category}</b><br>{escape(str(r.get('explanation', '')))}<br>"
                    f"<b>Likely severity:</b> {escape(str(r.get('severity')))} · <b>Affects:</b> {escape(affects)}<br>"
                    f"<small>Gemini estimate from the city category ({escape(str(r.get('assessed_by')))}), not verified.</small>")
        else:
            color, tooltip = "#2563eb", "Unverified city report (not assessed yet)"
            body = escape(str(r.get("explanation", "Unverified City report")))
        popup = folium.Popup(f"<b>City report #{title}</b><br>{body}", max_width=320)
        folium.CircleMarker(
            [r["lat"], r["lng"]], radius=9, color="white", weight=2, fill=True,
            fill_color=color, fill_opacity=1, popup=popup, tooltip=tooltip,
        ).add_to(m)
    if len(coords) > 1:
        m.fit_bounds([[min(p[0] for p in coords), min(p[1] for p in coords)],
                      [max(p[0] for p in coords), max(p[1] for p in coords)]])
    st_folium(m, height=460, use_container_width=True, key="get_it_done_city_demo", returned_objects=[])
