"""Optional Get It Done demo map for ClearPath (no impact on UCSD route engine)."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

import folium
import streamlit as st
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parent


def show_get_it_done_map() -> None:
    st.subheader("San Diego Get It Done · Demonstration")
    st.warning(
        "City resident reports (unverified), NOT UCSD campus obstacles, "
        "NOT Gemini photo analysis. No confirmed severity or accessibility impact. "
        "These reports do NOT affect ClearPath route recommendations."
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
    st.caption(f"Displaying {len(reports)} imported city service requests. Source: City of San Diego Open Data Portal.")
    coords = [(r["lat"], r["lng"]) for r in reports]
    avg_lat = sum(lat for lat, _ in coords) / len(coords)
    avg_lng = sum(lng for _, lng in coords) / len(coords)
    m = folium.Map(location=[avg_lat, avg_lng], zoom_start=13, tiles="OpenStreetMap")
    for r in reports:
        label = escape(str(r.get("explanation", "Unverified City report")))
        title = escape(str(r.get("source_id", "")))
        popup = folium.Popup(f"<b>City report #{title}</b><br>{label}", max_width=320)
        folium.Marker(
            [r["lat"], r["lng"]], popup=popup,
            tooltip="Unverified city report (not a confirmed hazard)",
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(m)
    if len(coords) > 1:
        m.fit_bounds([[min(p[0] for p in coords), min(p[1] for p in coords)],
                      [max(p[0] for p in coords), max(p[1] for p in coords)]])
    st_folium(m, height=460, use_container_width=True, key="get_it_done_city_demo", returned_objects=[])
