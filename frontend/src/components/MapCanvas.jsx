import {useEffect} from 'react';
import {Circle,CircleMarker,MapContainer,Marker,Polyline,Popup,TileLayer,useMap,useMapEvents,Tooltip} from 'react-leaflet';
import L from 'leaflet';
import {apiAsset} from '../api';

const TILES={
  streets:{url:'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',attribution:'&copy; OpenStreetMap contributors',subdomains:['a','b','c'],maxZoom:19},
  light:{url:'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',attribution:'&copy; OpenStreetMap &copy; CARTO',subdomains:['a','b','c','d'],maxZoom:20},
  satellite:{url:'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',attribution:'Tiles &copy; Esri and imagery contributors',subdomains:[],maxZoom:19}
};
function Bridge({mapRef,onBounds,pickMode,onPick,gps,followGps,route}){
  const map=useMap();
  useEffect(()=>{mapRef.current=map;const b=map.getBounds();onBounds([b.getSouth(),b.getWest(),b.getNorth(),b.getEast()])},[map,mapRef,onBounds]);
  useEffect(()=>{if(followGps && gps)map.panTo([gps.lat,gps.lng],{animate:true})},[gps?.lat,gps?.lng,followGps,map]);
  useEffect(()=>{if(route?.route?.points?.length>1){const b=L.latLngBounds(route.route.points);map.fitBounds(b.pad(0.30),{animate:true,maxZoom:17})}},[route,map]);
  useMapEvents({moveend(){const b=map.getBounds();onBounds([b.getSouth(),b.getWest(),b.getNorth(),b.getEast()])},click(e){if(pickMode)onPick({lat:e.latlng.lat,lng:e.latlng.lng})}});
  return null;
}
const markerIcon=L.divIcon({className:'gps-icon',html:'<div class="gps-dot"><div></div></div>',iconSize:[28,28],iconAnchor:[14,14]});
const destinationIcon=L.divIcon({className:'destination-icon',html:'<div class="dest-pin"><span>●</span></div>',iconSize:[32,40],iconAnchor:[16,37]});
const reportIcon=L.divIcon({className:'report-icon',html:'<div class="report-pin">+</div>',iconSize:[30,30],iconAnchor:[15,15]});
const COLORS={get_it_done:'#df8b3b',clearpath:'#0e8d82'};
export default function MapCanvas({mode='streets',gps,followGps,mapRef,onBounds,reports,clusters,showClusters,pickMode,onPick,reportPin,destination,route}){
  const tiles=TILES[mode]||TILES.streets;
  return <MapContainer center={[32.8797,-117.2376]} zoom={16} zoomControl={false} scrollWheelZoom={true} className="map-leaflet">
    <Bridge mapRef={mapRef} onBounds={onBounds} pickMode={pickMode} onPick={onPick} gps={gps} followGps={followGps} route={route}/>
    <TileLayer key={mode} {...tiles}/>
    {showClusters && clusters.map(c=><CircleMarker key={c.id} center={[c.lat,c.lng]} radius={Math.min(44,13+Math.sqrt(c.count)*4)} pathOptions={{color:'#4f8a86',weight:2,fillColor:'#a9d0c8',fillOpacity:0.27}}><Tooltip>{c.count} reports in this area · statistical cluster</Tooltip></CircleMarker>)}
    {reports.map(r=><CircleMarker key={r.id} center={[r.lat,r.lng]} radius={r.source==='clearpath'?9:6} pathOptions={{color:'#ffffff',weight:2,fillColor:COLORS[r.source]||'#64748b',fillOpacity:.96}}>
      <Popup minWidth={240} maxWidth={270}>
        <div className="hazard-popup">
          <div className="popup-eyebrow">{r.source==='clearpath'?'CLEARPATH COMMUNITY REPORT':'SAN DIEGO · GET IT DONE'}</div>
          <div className="popup-title">{r.category?.replaceAll('_',' ')||'Reported concern'}</div>
          <p>{r.description||'No description provided'}</p>
          {r.photo_url&&<img src={apiAsset(r.photo_url)} alt="Submitted obstacle" className="popup-photo"/>}
          <span className="popup-warning">Unverified report · not a confirmed closure</span>
          <div className="popup-muted">{r.status?`${r.status} · `:''}{r.created_at?.slice(0,10)||''}</div>
        </div>
      </Popup>
    </CircleMarker>)}
    {route?.baseline?.points?.length>1&&<Polyline positions={route.baseline.points} pathOptions={{color:'#a9afb2',weight:5,opacity:.65,dashArray:'9 9'}}/>}
    {route?.route?.points?.length>1&&<Polyline positions={route.route.points} pathOptions={{color:'#087d74',weight:7,opacity:.95}}/>}
    {destination&&<Marker position={[destination.lat,destination.lng]} icon={destinationIcon}><Popup>{destination.name||'Destination'}</Popup></Marker>}
    {reportPin&&<Marker position={[reportPin.lat,reportPin.lng]} icon={reportIcon}><Popup>Selected report location</Popup></Marker>}
    {gps&&<><Circle center={[gps.lat,gps.lng]} radius={Math.min(gps.accuracy||15,250)} pathOptions={{color:'#247ad1',fillColor:'#63a5ff',fillOpacity:.09,weight:1}}/><Marker position={[gps.lat,gps.lng]} icon={markerIcon}><Tooltip permanent={false}>{gps.kind==='demo'?'Demo start (not GPS)':'Live device location'}</Tooltip></Marker></>}
  </MapContainer>
}
