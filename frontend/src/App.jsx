import {useCallback,useEffect,useRef,useState} from 'react';
import {Accessibility,AlertCircle,ArrowRight,ArrowUpRight,Camera,Check,ChevronDown,ChevronRight,Compass,Flag,Footprints,Layers3,LocateFixed,Map as MapIcon,MapPin,Menu,Minus,Navigation,Plus,Search,Send,ShieldAlert,SlidersHorizontal, Sparkles, X, Eye, Info, RefreshCw} from 'lucide-react';
import MapCanvas from './components/MapCanvas.jsx';
import {api} from './api.js';
import {useLiveLocation} from './hooks/useLiveLocation.js';

const PROFILES=[{id:'standard',label:'Standard walking',hint:'General pedestrian routes',icon:'🚶'},{id:'wheelchair',label:'Wheelchair',hint:'Step-free routing profile',icon:'♿'},{id:'cane',label:'Cane / walker',hint:'Consider uneven terrain',icon:'🦯'},{id:'crutches',label:'Crutches',hint:'Avoid steps where supported',icon:'🩼'},{id:'low_vision',label:'Low vision',hint:'Consider lighting and obstacles',icon:'👁'}];
const CATEGORY=[['sidewalk','Damaged sidewalk'],['ramp','Blocked ramp'],['elevator','Elevator out of service'],['construction','Construction / closure'],['debris','Debris / obstruction'],['lighting','Lighting / visibility'],['stairs','Stairs / inaccessible step'],['slope','Steep slope'],['safety_concern','Other pedestrian safety concern'],['other','Other obstacle']];
const titleCase=s=>(s||'').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
const fmtDistance=n=>n==null?'—':n>=1000?(n/1000).toFixed(1)+' km':n+' m';
const fmtDuration=n=>n==null?'—':Math.max(1,Math.round(n/60))+' min';
const pause=ms=>new Promise(r=>setTimeout(r,ms));
function Logo(){return <div className="brand"><div className="brand-mark"><div className="brand-track"/></div><div className="brand-copy"><strong>clearpath<span className="brand-period">.</span></strong><span>SAN DIEGO ACCESS MAP</span></div></div>}
function StatusDot({ok}){return <span className={'status-dot '+(ok?'on':'off')}/>}
function MapButton({children,title,onClick,active=false}){return <button className={'map-button '+(active?'active':'')} aria-label={title} title={title} onClick={onClick}>{children}</button>}
function Pill({children,green=false}){return <span className={'status-pill '+(green?'green':'')}>{children}</span>}
export default function App(){
  const mapRef=useRef(null);
  const {location:gps,status:gpsStatus,error:gpsError,start:startGps,stop:stopGps,useDemo}=useLiveLocation();
  const [sheetOpen,setSheetOpen]=useState(true);
  const [followLocation,setFollowLocation]=useState(false);
  const [tab,setTab]=useState('route');
  const [profile,setProfile]=useState('wheelchair');
  const [mapMode,setMapMode]=useState('streets');
  const [layerOpen,setLayerOpen]=useState(false);
  const [source,setSource]=useState('all');
  const [clustersOn,setClustersOn]=useState(false);
  const [pickMode,setPickMode]=useState(null);
  const [reportPin,setReportPin]=useState(null);
  const [destination,setDestination]=useState(null);
  const [search,setSearch]=useState('');
  const [suggestions,setSuggestions]=useState([]);
  const [searchLoading,setSearchLoading]=useState(false);
  const [bbox,setBbox]=useState([32.86,-117.26,32.91,-117.21]);
  const [reports,setReports]=useState([]);
  const [clusters,setClusters]=useState([]);
  const [health,setHealth]=useState(null);
  const [route,setRoute]=useState(null);
  const [routeLoading,setRouteLoading]=useState(false);
  const [routeError,setRouteError]=useState('');
  const [formCategory,setFormCategory]=useState('sidewalk');
  const [formDescription,setFormDescription]=useState('');
  const [photo,setPhoto]=useState(null);
  const [reportLoading,setReportLoading]=useState(false);
  const [reportMessage,setReportMessage]=useState(null);
  const [dataVersion,setDataVersion]=useState(0);
  const [feedbackSent,setFeedbackSent]=useState(false);
  const onBounds=useCallback(b=>setBbox(old=>old.every((x,i)=>Math.abs(x-b[i])<.0004)?old:b),[]);
  const selectMapPoint=useCallback(p=>{
    if(pickMode==='destination'){setDestination({...p,name:'Pinned destination'});setSearch('Pinned destination');setRoute(null)}
    if(pickMode==='report'){setReportPin(p);setTab('report')}
    setPickMode(null);setSheetOpen(true);
  },[pickMode]);
  useEffect(()=>{api('/api/health').then(setHealth).catch(()=>setHealth(null))},[dataVersion]);
  useEffect(()=>{let active=true;const controller=new AbortController();
    const timer=setTimeout(async()=>{
      try{
        const [s,w,n,e]=bbox;
        const q=new URLSearchParams({south:s,west:w,north:n,east:e,profile,source,limit:900});
        const rows=await api('/api/reports?'+q);
        if(active)setReports(rows.reports||[]);
      }catch(e){if(active)console.warn(e.message)}
    },280);
    return()=>{active=false;clearTimeout(timer);controller.abort()};
  },[bbox,profile,source,dataVersion]);
  useEffect(()=>{if(!clustersOn){setClusters([]);return}let active=true;
    const timer=setTimeout(async()=>{try{const [s,w,n,e]=bbox;const rows=await api('/api/clusters?'+new URLSearchParams({south:s,west:w,north:n,east:e,profile}));if(active)setClusters(rows.clusters||[])}catch{}},350);
    return()=>{active=false;clearTimeout(timer)};
  },[bbox,profile,clustersOn,dataVersion]);
  const chooseProfile=id=>{setProfile(id);setRoute(null);setRouteError('');setFeedbackSent(false)};
  async function doSearch(e){e?.preventDefault();if(search.trim().length<2)return;
    setSearchLoading(true);try{const r=await api('/api/places?q='+encodeURIComponent(search.trim()));setSuggestions(r.places||[])}catch(err){setRouteError(err.message)}finally{setSearchLoading(false)}
  }
  function chooseDestination(p){setDestination(p);setSearch(p.name);setSuggestions([]);setRoute(null);setRouteError('');mapRef.current?.flyTo([p.lat,p.lng],15)}
  async function doRoute(demo=false){
    setRouteError('');setFeedbackSent(false);setRouteLoading(true);
    try{
      if(!demo&&!gps)throw Error('Enable GPS or tap “Use demo start” to set your starting point.');
      if(!demo&&!destination)throw Error('Search for a destination or pin one on the map.');
      const payload={start:{lat:gps?.lat||32.87965,lng:gps?.lng||-117.23758},
       destination:{lat:destination?.lat||32.88072,lng:destination?.lng||-117.23763},profile,demo};
      const result=await api('/api/route',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      setRoute(result);setTab('route');setSheetOpen(true);
    }catch(err){setRouteError(err.message)}finally{setRouteLoading(false)}
  }
  async function submitReport(e){e.preventDefault();setReportMessage(null);
    const pin=reportPin||gps;
    if(!pin){setReportMessage({error:true,text:'Turn on location or tap the map to pinpoint the obstacle.'});return}
    if(!reportPin&&gps?.kind==='demo'){setReportMessage({error:true,text:'Demo GPS is not a real obstacle location. Tap the map to mark where you observed the issue.'});return}
    if(!formDescription.trim()&&!photo){setReportMessage({error:true,text:'Please add a description or image.'});return}
    const data=new FormData();data.append('lat',String(pin.lat));data.append('lng',String(pin.lng));data.append('category',formCategory);data.append('description',formDescription);
    if(photo)data.append('photo',photo);
    setReportLoading(true);
    try{const result=await api('/api/reports',{method:'POST',body:data});
      setReportMessage({error:false,text:`Report submitted (${result.id}). ${result.ai_status==='gemini_photo'?'Gemini reviewed the photo; findings remain unverified.':'Recorded as an unverified community observation.'}`});
      setReportPin(null);setPhoto(null);setFormDescription('');setDataVersion(v=>v+1);setRoute(null);
    }catch(err){setReportMessage({error:true,text:err.message})}finally{setReportLoading(false)}
  }
  async function sendFeedback(helpful){if(!route||feedbackSent)return;
    try{await api('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({route_id:route.route.id,profile,helpful})});setFeedbackSent(true)}catch{}
  }
  const userCanLocate=gpsStatus==='tracking';
  const profileName=PROFILES.find(p=>p.id===profile)?.label||'Profile';
  const reportLocation=reportPin||gps;
  return <main className="app-shell">
    <div className="map-region">
      <MapCanvas mode={mapMode} gps={gps} followGps={followLocation} mapRef={mapRef} onBounds={onBounds} reports={reports} clusters={clusters}
        showClusters={clustersOn} pickMode={pickMode} onPick={selectMapPoint} reportPin={reportPin} destination={destination} route={route}/>
      <div className="map-top-controls">
        <div className="layer-holder">
          <MapButton title="Map styles and layers" active={layerOpen} onClick={()=>setLayerOpen(v=>!v)}><Layers3 size={20}/></MapButton>
          {layerOpen&&<div className="layers-panel">
            <div className="layers-heading">MAP STYLE</div>
            <div className="tile-grid">{['streets','light','satellite'].map(m=><button key={m} className={'tile-option tile-'+m+' '+(mapMode===m?'chosen':'')} onClick={()=>setMapMode(m)}><span className="tile-thumb"/><span>{m==='streets'?'Streets':m==='light'?'Minimal':'Satellite'}</span></button>)}</div>
            <div className="layers-heading extra">DATA LAYERS</div>
            <label className="checkbox-row"><input type="checkbox" checked={clustersOn} onChange={e=>setClustersOn(e.target.checked)}/> Report clusters <span className="soon-dot">AI + GIS</span></label>
            <div className="source-choices">{[['all','All'],['get_it_done','City'],['clearpath','Community']].map(([id,name])=><button key={id} className={source===id?'on':''} onClick={()=>setSource(id)}>{name}</button>)}</div>
          </div>}
        </div>
        <div className="zoom-stack"><MapButton title="Zoom in" onClick={()=>mapRef.current?.zoomIn()}><Plus size={20}/></MapButton><div className="zoom-div"/><MapButton title="Zoom out" onClick={()=>mapRef.current?.zoomOut()}><Minus size={20}/></MapButton></div>
        <MapButton title={followLocation?"Stop following location":"Center and follow my location"} active={followLocation} onClick={()=>{if(!gps){startGps();setFollowLocation(true)}else{mapRef.current?.flyTo([gps.lat,gps.lng],17);setFollowLocation(v=>!v)}}}><LocateFixed size={20}/></MapButton>
      </div>
      {pickMode&&<div className="map-pick-tip"><MapPin size={17}/> Tap the map to select {pickMode==='report'?'obstacle location':'destination'} <button onClick={()=>setPickMode(null)} aria-label="Cancel map selection"><X size={16}/></button></div>}
      <div className="map-data-legend"><span className="legend-dot teal"/> Community <span className="legend-dot amber"/> City reported <span className="legend-divider"/> {reports.length} visible</div>
    </div>
    <header className="mobile-top"><Logo/><button aria-label="Open navigation panel" onClick={()=>setSheetOpen(v=>!v)}><Menu/></button></header>
    <aside className={'side-panel '+(sheetOpen?'sheet-open':'sheet-closed')}>
      <div className="sheet-handle" onClick={()=>setSheetOpen(v=>!v)} role="button" aria-label="Toggle panel" tabIndex="0" onKeyDown={e=>{if(e.key==='Enter')setSheetOpen(v=>!v)}}><div/></div>
      <div className="panel-header"><Logo/><div className="live-badge"><StatusDot ok={!!health}/> {health?'DATA CONNECTED':'CONNECTING'}</div></div>
      <div className="panel-content">
        <div className="intro-label"><span className="tiny-star">✦</span> COMMUNITY-POWERED ACCESSIBILITY</div>
        <h1>Go further.<br/><span>Your way.</span></h1>
        <p className="intro-copy">Find routes informed by real, local accessibility reports across San Diego.</p>
        <div className="panel-tabs" role="tablist" aria-label="Main sections">
          {[['route',Navigation,'Plan route'],['report',Flag,'Report'],['insights',SlidersHorizontal,'Insights']].map(([id,Icon,name])=><button role="tab" aria-selected={tab===id} key={id} className={tab===id?'selected':''} onClick={()=>{setTab(id);setSheetOpen(true)}}><Icon size={16}/>{name}</button>)}
        </div>
        {tab==='route'&&<section className="tab-content">
          <div className="section-title"><h2>Plan your journey</h2><span className="section-step">01 / 03</span></div>
          <div className="field-label">YOUR STARTING POINT</div>
          <div className="current-location-card"><div className="loc-icon"><LocateFixed size={19}/></div><div className="loc-body"><strong>{gps?.kind==='demo'?'Price Center (demo location)':userCanLocate?'Your live location':'Current location'}</strong><span>{userCanLocate?`Tracking · ±${Math.round(gps?.accuracy||0)} m accuracy`:gps?.kind==='demo'?'Demo GPS — not your real location':'Enable device location to start'}</span></div><button className="small-locate" aria-label="Enable location tracking" onClick={startGps}><RefreshCw size={15}/></button></div>
          {!userCanLocate&&<div className="location-actions"><button onClick={startGps}><LocateFixed size={15}/> Enable live GPS</button><button onClick={useDemo}>Use demo start</button></div>}
          {gpsError&&<p className="inline-error">{gpsError}</p>}
          <div className="travel-line"><span/><span/><span/></div>
          <label className="field-label" htmlFor="destination-search">WHERE TO?</label>
          <form className="search-box" onSubmit={doSearch}><Search size={19}/><input id="destination-search" placeholder="Search a destination in San Diego" value={search} onChange={e=>{setSearch(e.target.value);if(suggestions.length)setSuggestions([])}}/><button type="submit" aria-label="Search locations">{searchLoading?<span className="spin"/>:<ArrowRight size={18}/>}</button></form>
          {suggestions.length>0&&<div className="search-results">{suggestions.map((p,i)=><button key={i} onClick={()=>chooseDestination(p)}><MapPin size={17}/><span><strong>{p.name}</strong>{p.subtitle&&<small>{p.subtitle}</small>}</span><ChevronRight size={16}/></button>)}</div>}
          <button className="text-link" onClick={()=>{setPickMode('destination');setSheetOpen(false)}}><MapPin size={15}/> Or choose destination on the map <ArrowUpRight size={14}/></button>
          {destination&&<div className="destination-picked"><Check size={14}/>{destination.name||'Selected location'}</div>}
          <div className="field-label with-space">ACCESSIBILITY PREFERENCE</div>
          <div className="select-shell"><div className="select-symbol"><Accessibility size={20}/></div><select aria-label="Mobility profile" value={profile} onChange={e=>chooseProfile(e.target.value)}>{PROFILES.map(p=><option key={p.id} value={p.id}>{p.label}</option>)}</select><ChevronDown size={17}/></div>
          <div className="profile-hint">{PROFILES.find(p=>p.id===profile)?.hint} · personalized reported-obstacle filters</div>
          <button disabled={routeLoading} className="primary-action" onClick={()=>doRoute(false)}>{routeLoading?<><span className="spin light"/> Calculating...</>:<><Navigation size={19}/> Find my route <ArrowRight size={18}/></>}</button>
          <button className="demo-link" disabled={routeLoading} onClick={()=>doRoute(true)}>▶ Try a campus route demo (no routing key)</button>
          {routeError&&<div className="message warning"><AlertCircle size={17}/>{routeError}</div>}
          {!health?.routing_configured&&<p className="small-print">Real citywide routes require an OpenRouteService API key on the server; the campus demo works without one.</p>}
          {route&&<div className="route-result"><div className="result-overline"><Sparkles size={15}/> {route.mode==='demo'?'ILLUSTRATIVE CAMPUS DEMO':'ACCESS-AWARE ROUTE'}</div>
             <div className="route-metrics"><div><strong>{fmtDuration(route.route.duration_s)}</strong><span>Est. time</span></div><div><strong>{fmtDistance(route.route.distance_m)}</strong><span>Distance</span></div><div><strong>{route.alerts.length}</strong><span>Initial route reports</span></div></div>
             <p className="route-explanation">{route.explanation}</p>
             {route.changed&&<div className="detour-banner"><Navigation size={16}/> Alternative route found based on reported concerns</div>}
             {route.warning&&<div className="message warning">{route.warning}</div>}
             <div className="route-caveat"><Info size={16}/>{route.caveat}</div>
             {route.alerts.length>0&&<div className="route-alerts"><strong>Reported concerns near initial path</strong>{route.alerts.slice(0,3).map(a=><div key={a.id}><span>• {titleCase(a.category)}</span><small>~{a.distance_m} m from path</small></div>)}</div>}
             <div className="feedback"><span>Was this helpful?</span>{feedbackSent?<small>Thanks for your feedback.</small>:<><button onClick={()=>sendFeedback(true)} aria-label="Route helpful">👍</button><button onClick={()=>sendFeedback(false)} aria-label="Route not helpful">👎</button></>}</div>
           </div>}
        </section>}
        {tab==='report'&&<section className="tab-content">
          <div className="section-title"><h2>Report an obstacle</h2><span className="section-step">02 / 03</span></div>
          <p className="form-lead">Spotted a blocked path, damaged pavement, or another pedestrian concern? Share an observation to help neighbors investigate.</p>
          <form onSubmit={submitReport}>
            {!health?.gemini_configured&&<div className="message warning"><Info size={16}/> Gemini is not configured. Reports will be saved as unverified community submissions without photo analysis.</div>}
            <label className="field-label" htmlFor="report-category">WHAT HAPPENED?</label>
            <div className="select-shell report-select"><div className="select-symbol"><ShieldAlert size={18}/></div><select id="report-category" value={formCategory} onChange={e=>setFormCategory(e.target.value)}>{CATEGORY.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select><ChevronDown size={16}/></div>
            <label className="field-label with-space" htmlFor="report-text">DESCRIPTION</label>
            <textarea id="report-text" value={formDescription} onChange={e=>setFormDescription(e.target.value.slice(0,600))} rows={4} placeholder="Describe the obstacle and how it affects the path…"/>
            <div className="hint-row"><span>Keep identifying details about other people out.</span><span>{formDescription.length}/600</span></div>
            <label className="upload-box"><Camera size={22}/><span>{photo?photo.name:'Add a photo (optional)'}</span><small>Camera or photo gallery · up to 8 MB</small><input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>setPhoto(e.target.files?.[0]||null)}/></label>
            <div className="report-loc"><div><MapPin size={18}/><div><strong>Report location</strong><small>{reportLocation?`${reportLocation.lat.toFixed(5)}, ${reportLocation.lng.toFixed(5)}${reportPin?' · chosen on map':gps?.kind==='demo'?' · demo start':' · GPS'}`:'Location not set'}</small></div></div><button type="button" onClick={()=>{setPickMode('report');setSheetOpen(false)}}>Pin on map</button></div>
            {reportLocation&&<div className="location-privacy"><Info size={14}/> GPS can be imprecise around buildings. Verify the obstacle location before sending.</div>}
            {gps?.kind==='demo'&&!reportPin&&<div className="message warning">Demo start cannot be used for reporting. Pin the actual obstacle location on the map.</div>}
            <button className="primary-action" disabled={reportLoading} type="submit">{reportLoading?<><span className="spin light"/> Analyzing / saving…</>:<><Send size={18}/> Submit community report <ArrowRight size={18}/></>}</button>
            {reportMessage&&<div className={'message '+(reportMessage.error?'warning':'success')}>{reportMessage.error?<AlertCircle size={17}/>:<Check size={17}/>} {reportMessage.text}</div>}
          </form><p className="small-print">Reports are community submissions, not emergency dispatch. If danger is immediate, follow campus/public emergency procedures. Avoid sharing bystanders' faces or private information.</p>
        </section>}
        {tab==='insights'&&<section className="tab-content"><div className="section-title"><h2>Community insights</h2><span className="section-step">03 / 03</span></div>
          <div className="insight-hero"><div className="insight-icon"><MapIcon size={21}/></div><div><div className="big-number">{health?.city_reports?.toLocaleString()||'—'}</div><span>San Diego city requests in demo dataset</span></div></div>
          <div className="insight-tiles"><div><strong>{health?.community_reports||0}</strong><span>ClearPath reports</span></div><div><strong>{reports.length}</strong><span>Visible on map</span></div></div>
          <label className="insight-toggle"><div><strong>Display report clusters</strong><p>Find areas with repeated reports using DBSCAN.</p></div><input type="checkbox" checked={clustersOn} onChange={e=>setClustersOn(e.target.checked)}/></label>
          <div className="insight-info"><Info size={18}/><p>Get It Done contains service requests made by residents. A request does not independently prove an obstacle, severity, or accessible route closure.</p></div>
          <button className="outline-action" onClick={()=>{mapRef.current?.flyTo([32.87965,-117.23758],14);setSource('all')}}><Compass size={17}/> Explore UCSD-area reports</button>
        </section>}
      </div>
      <footer className="panel-footer"><div><span className="source-mark"/> Powered by <strong>San Diego Open Data</strong> + community reports</div><p>Reported concerns only. Never assume a displayed route is verified accessible.</p></footer>
    </aside>
    <div className="mobile-bottom-nav"><button className={tab==='route'?'active':''} onClick={()=>{setTab('route');setSheetOpen(true)}}><Navigation size={19}/>Routes</button><button className={tab==='report'?'active':''} onClick={()=>{setTab('report');setSheetOpen(true)}}><Flag size={19}/>Report</button><button className={tab==='insights'?'active':''} onClick={()=>{setTab('insights');setSheetOpen(true)}}><SlidersHorizontal size={19}/>Insights</button></div>
  </main>;
}
