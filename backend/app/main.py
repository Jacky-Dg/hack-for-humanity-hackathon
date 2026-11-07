from __future__ import annotations
import json, time, threading
from pathlib import Path
from functools import lru_cache
from typing import Literal
import httpx
import numpy as np
from sklearn.cluster import DBSCAN
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .config import CORS, PHOTOS, GEMINI_KEY, ORS_KEY
from .city import all_reports, get_city, viewport, affects_profile
from .storage import create_report, save_feedback, get_community
from .routing import find_route, campus_demo
from .analysis import inspect_photo

app=FastAPI(title='ClearPath API',version='2.0.0')
app.add_middleware(CORSMiddleware,allow_origins=CORS,allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['*'])
app.mount('/photos',StaticFiles(directory=PHOTOS),name='photos')
PROFILES={'standard','wheelchair','cane','crutches','low_vision'}
CATEGORIES={'sidewalk','ramp','elevator','construction','debris','lighting','stairs','slope','safety_concern','other'}

class Position(BaseModel):
    lat:float=Field(ge=-90,le=90)
    lng:float=Field(ge=-180,le=180)
class RouteRequest(BaseModel):
    start:Position
    destination:Position
    profile:Literal['standard','wheelchair','cane','crutches','low_vision']='wheelchair'
    demo:bool=False
class FeedbackRequest(BaseModel):
    route_id:str=Field(max_length=60)
    profile:str=Field(max_length=30)
    helpful:bool

@app.get('/api/health')
def health():
    return {'ok':True,'city_reports':len(get_city()),'community_reports':len(get_community()),
            'gemini_configured':bool(GEMINI_KEY),'routing_configured':bool(ORS_KEY)}

@app.get('/api/reports')
def reports(south:float=32.5,west:float=-117.6,north:float=33.2,east:float=-116.6,
            profile:str='standard',source:str='all',limit:int=Query(1500,ge=1,le=3500)):
    if profile not in PROFILES or source not in {'all','get_it_done','clearpath'}:raise HTTPException(422,'Invalid filter')
    if not (south<north and west<east):raise HTTPException(422,'Invalid viewport')
    return {'reports':viewport(all_reports(),(south,west,north,east),profile,source,limit),
            'total_city':len(get_city()),'total_community':len(get_community())}

@app.get('/api/clusters')
def clusters(south:float=32.5,west:float=-117.6,north:float=33.2,east:float=-116.6,
             profile:str='standard'):
    if profile not in PROFILES or not(south<north and west<east):raise HTTPException(422,'Invalid filter')
    rows=viewport(all_reports(),(south,west,north,east),profile,'all',limit=3500)
    if len(rows)<4:return {'clusters':[]}
    coords=np.radians(np.array([[r['lat'],r['lng']] for r in rows]))
    labels=DBSCAN(eps=0.13/6371.0088,min_samples=4,metric='haversine').fit_predict(coords)
    groups=[]
    for label in set(labels):
        if label<0:continue
        members=[rows[i] for i,l in enumerate(labels) if l==label]
        groups.append({'id':int(label),'lat':sum(x['lat'] for x in members)/len(members),
                       'lng':sum(x['lng'] for x in members)/len(members),'count':len(members),
                       'categories':sorted({x['category'] for x in members})[:5]})
    return {'clusters':sorted(groups,key=lambda x:-x['count'])[:35]}

PLACE_INDEX=[
  {'name':'UCSD Price Center','lat':32.87965,'lng':-117.23758},
  {'name':'Geisel Library, UCSD','lat':32.88072,'lng':-117.23763},
  {'name':'UCSD Central Campus Station','lat':32.87827,'lng':-117.23186},
  {'name':'UCSD Jacobs School of Engineering','lat':32.8811,'lng':-117.2347},
  {'name':'Balboa Park, San Diego','lat':32.7311,'lng':-117.1465},
  {'name':'San Diego City Hall','lat':32.7168,'lng':-117.1621},
  {'name':'La Jolla Shores','lat':32.8504,'lng':-117.2726},
]
_last_geocode=[0.0]
_geo_lock=threading.Lock()
@lru_cache(maxsize=80)
def nominatim(query):
    # Public Nominatim policy: at most 1 request/second, meaningful User-Agent, explicit submit only.
    with _geo_lock:
        delay=max(0,1.1-(time.monotonic()-_last_geocode[0]))
        if delay:time.sleep(delay)
        _last_geocode[0]=time.monotonic()
    try:
        r=httpx.get('https://nominatim.openstreetmap.org/search',
                    params={'q':query+', San Diego County, California','format':'json','limit':4,'countrycodes':'us'},
                    headers={'User-Agent':'ClearPathHackForHumanityUCSD/2.0 (noncommercial accessibility project)'},timeout=8)
        r.raise_for_status()
        return [{'name':i['display_name'].split(',')[0], 'subtitle':i['display_name'][:110],
                 'lat':float(i['lat']),'lng':float(i['lon'])} for i in r.json()]
    except Exception:return []

@app.get('/api/places')
def places(q:str=Query(min_length=2,max_length=80)):
    key=q.strip().lower()
    local=[p for p in PLACE_INDEX if key in p['name'].lower()]
    if len(local)>=2:return {'places':local[:5]}
    more=nominatim(key)
    return {'places':(local+more)[:5]}

@app.post('/api/route')
def route(req:RouteRequest):
    if req.demo:return campus_demo(req.profile,all_reports())
    return find_route([req.start.lat,req.start.lng],[req.destination.lat,req.destination.lng],req.profile)

@app.post('/api/reports')
async def submit_report(lat:float=Form(...),lng:float=Form(...),
                        category:str=Form('other'),description:str=Form(''),
                        photo:UploadFile|None=File(None)):
    if not (32.5<=lat<=33.2 and -117.6<=lng<=-116.6):raise HTTPException(422,'Reports must be in San Diego')
    if category not in CATEGORIES:raise HTTPException(422,'Invalid category')
    if len(description)>600:raise HTTPException(422,'Description is too long (600 character limit)')
    if not description.strip() and photo is None:raise HTTPException(422,'Enter a description or upload a photo')
    data=None
    if photo:
        data=await photo.read(8*1024*1024+1)
        if len(data)>8*1024*1024:raise HTTPException(413,'Maximum image size is 8 MB')
    impacts=dict.fromkeys(['wheelchair','cane','crutches','low_vision'],True)
    severity='unknown'; ai_status='user_report';final_category=category
    if data and GEMINI_KEY:
        try:
            ai=inspect_photo(data,description)
            if not ai['is_obstacle']:raise HTTPException(422,'Gemini did not detect a reportable obstacle. Add a clear description or choose another photo.')
            impacts=ai['affects'];severity=ai['severity'];final_category=ai['category'];ai_status='gemini_photo'
            if not description.strip():description=ai['explanation']
        except HTTPException:raise
        except Exception as exc:raise HTTPException(502,'Gemini photo analysis unavailable. Try submitting a text-only report.') from exc
    # Text-only remains explicitly user-submitted and unverified; no made-up AI classifications.
    try: return create_report(lat=lat,lng=lng,category=final_category,description=description.strip() or 'Photo-backed potential obstruction',
                             profile_impacts=impacts,image=data,ai_status=ai_status,severity=severity)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@app.post('/api/feedback')
def feedback(request:FeedbackRequest):
    if request.profile not in PROFILES:raise HTTPException(422,'Invalid profile')
    return save_feedback(request.route_id,request.profile,request.helpful)


# Optional single-origin production hosting: build React first (`npm run build`).
# API routes and photo uploads remain under /api and /photos.
DIST = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if DIST.is_dir():
    app.mount('/assets', StaticFiles(directory=DIST / 'assets'), name='frontend-assets')

    @app.get('/{full_path:path}', include_in_schema=False)
    def frontend_app(full_path: str):
        requested = (DIST / full_path).resolve()
        if requested.is_relative_to(DIST) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(DIST / 'index.html')
