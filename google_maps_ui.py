"""Google routing and map display. Keys stay out of the repository."""
import html
import json
import os
from urllib.parse import urlencode

import requests
import streamlit as st
import streamlit.components.v1 as components


def setting(name):
    value = os.environ.get(name, "")
    if value:
        return value
    try:
        return str(st.secrets.get(name, ""))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ""


def map_location(value):
    from routes import START, END, START_NAME, END_NAME
    if value in {START_NAME, END_NAME}:
        point = START if value == START_NAME else END
        return {"location": {"latLng": {"latitude": point[0], "longitude": point[1]}}}
    return {"address": value if "san diego" in value.lower() else value + ", UC San Diego"}


def map_query(value):
    location = map_location(value)
    if "address" in location:
        return location["address"]
    point = location["location"]["latLng"]
    return f"{point['latitude']},{point['longitude']}"


def directions_url(origin, destination):
    return "https://www.google.com/maps/dir/?" + urlencode({
        "api": "1", "origin": map_query(origin), "destination": map_query(destination), "travelmode": "walking"})


def decode_polyline(encoded):
    index = lat = lng = 0
    points = []
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            result = shift = 0
            while True:
                if index >= len(encoded) or shift > 30:
                    raise ValueError("Invalid route geometry")
                value = ord(encoded[index]) - 63
                index += 1
                result |= (value & 31) << shift
                shift += 5
                if value < 32:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lng += deltas[1]
        points.append((lat / 1e5, lng / 1e5))
    return points


def fetch_routes(origin, destination, key):
    response = requests.post(
        "https://routes.googleapis.com/directions/v2:computeRoutes",
        headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask":
                 "routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline"},
        json={"origin": map_location(origin), "destination": map_location(destination),
              "travelMode": "WALK", "computeAlternativeRoutes": True,
              "polylineQuality": "HIGH_QUALITY", "units": "METRIC"}, timeout=20)
    if not response.ok:
        raise ValueError(f"Google Routes request failed (HTTP {response.status_code}). Check Routes API, billing, and key restrictions.")
    routes = []
    for index, route in enumerate(response.json().get("routes", [])):
        points = decode_polyline(route.get("polyline", {}).get("encodedPolyline", ""))
        if len(points) < 2:
            continue
        routes.append({"id": f"google_{index}", "name": f"Google walking route {index + 1}",
                       "points": points, "distance_m": route["distanceMeters"],
                       "duration": route.get("duration"), "source": "Google Maps",
                       "verified": False, "start_name": origin, "end_name": destination})
    if not routes:
        raise ValueError("Google returned no walking routes. Try a more specific campus location.")
    return routes


def render_google_map(routes, reports, selected_id, key):
    # Encode data as JSON and escape '<' to prevent report text ending the script.
    data = json.dumps({"routes": routes, "reports": reports, "selected": selected_id}).replace("<", "\\u003c")
    script_url = "https://maps.googleapis.com/maps/api/js?" + urlencode({"key": key, "callback": "initMap", "loading": "async"})
    markup = '''<html><head><style>html,body,#map{height:100%;margin:0;font-family:sans-serif}</style></head>
<body><div id="map"></div><script>
const data = DATA;
window.gm_authFailure = function(){document.getElementById('map').textContent='Google Maps authorization failed. Check the browser key, Maps JavaScript API, billing and allowed referrers.';};
window.initMap = async function(){
 const {Map, Polyline, InfoWindow} = await google.maps.importLibrary('maps');
 const {AdvancedMarkerElement, PinElement} = await google.maps.importLibrary('marker');
 const map = new Map(document.getElementById('map'),{center:{lat:32.8802,lng:-117.2376},zoom:16,mapId:'DEMO_MAP_ID'});
 const bounds = new google.maps.LatLngBounds();
 for(const route of data.routes){
  const path=route.points.map(p=>({lat:p[0],lng:p[1]}));
  for(const p of path)bounds.extend(p);
  new Polyline({map,path,strokeColor:route.id===data.selected?'#075985':'#64748b',strokeWeight:route.id===data.selected?7:4});
 }
 if(data.routes.length){
  const r=data.routes[0];
  for(const [p,label] of [[r.points[0],r.start_name],[r.points[r.points.length-1],r.end_name]]){
   new AdvancedMarkerElement({map,position:{lat:p[0],lng:p[1]},title:label});
  }
 }
 for(const report of data.reports){
  const color={impassable:'#dc2626',difficult:'#c2410c',minor:'#15803d'}[report.severity]||'#64748b';
  const pin=new PinElement({background:color,borderColor:'#fff',glyphColor:'#fff'});
  const marker=new AdvancedMarkerElement({map,position:{lat:report.lat,lng:report.lng},content:pin.element,title:report.type});
  const content=document.createElement('div');
  content.style.maxWidth='280px';
  content.textContent=report.severity+' — '+report.explanation;
  const popup=new InfoWindow({content});
  marker.addListener('click',()=>popup.open({map,anchor:marker}));
 }
 if(data.routes.length)map.fitBounds(bounds,45);
};
</script><script async src="SCRIPT_URL"></script></body></html>'''
    components.html(markup.replace("DATA", data).replace("SCRIPT_URL", html.escape(script_url, quote=True)), height=580)
