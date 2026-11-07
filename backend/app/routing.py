"""Real pedestrian routing with ORS; hazards affect precautionary detours, not promises of safety.
When no ORS API key exists, only clearly labeled campus DEMO polylines are available.
"""
from __future__ import annotations
import math
import httpx
from fastapi import HTTPException
from .config import ORS_KEY
from .city import affects_profile, all_reports
from .analysis import explain_route

PROFILE_MAP={'standard':'foot-walking','wheelchair':'wheelchair','cane':'foot-walking','crutches':'foot-walking','low_vision':'foot-walking'}

def haversine(a,b):
    lat1,lon1=map(math.radians,a);lat2,lon2=map(math.radians,b)
    v=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 12742000*math.asin(min(1,math.sqrt(v)))

def point_to_segment(point,a,b):
    k=math.cos(math.radians(point[0]))
    ax=(a[1]-point[1])*111320*k; ay=(a[0]-point[0])*111320
    bx=(b[1]-point[1])*111320*k; by=(b[0]-point[0])*111320
    dx=bx-ax;dy=by-ay
    t=max(0,min(1,-(ax*dx+ay*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
    return math.hypot(ax+dx*t,ay+dy*t)

def distance_to_polyline(point,points):
    if len(points)<2:return float('inf')
    return min(point_to_segment(point,a,b) for a,b in zip(points,points[1:]))

def hazards_near(points,reports,profile,threshold=32):
    return sorted([{**r,'distance_m':distance_to_polyline([r['lat'],r['lng']],points)} for r in reports
                   if affects_profile(r,profile) and haversine([r['lat'],r['lng']],points[0]) < 20000
                   and distance_to_polyline([r['lat'],r['lng']],points) <= threshold],key=lambda r:r['distance_m'])

def bounding_square(lat,lng,radius_m):
    y=radius_m/111320;x=radius_m/(111320*max(.3,math.cos(math.radians(lat))))
    return [[[lng-x,lat-y],[lng+x,lat-y],[lng+x,lat+y],[lng-x,lat+y],[lng-x,lat-y]]]

def avoid_polygons(alerts,start,end):
    coords=[]
    for r in alerts:
        if len(coords)>=8:break
        p=[r['lat'],r['lng']]
        if haversine(p,start)<35 or haversine(p,end)<35:continue
        radius=18 if r['source']=='clearpath' else 12
        coords.append(bounding_square(r['lat'],r['lng'],radius))
    return {'type':'MultiPolygon','coordinates':coords} if coords else None

def ors_request(start,end,profile,avoid=None):
    params={'coordinates':[[start[1],start[0]],[end[1],end[0]]], 'instructions':False}
    if profile in {'cane','crutches'}: params['options']={'avoid_features':['steps']}
    if avoid:
        params.setdefault('options',{})['avoid_polygons']=avoid
    try:
        result=httpx.post(f'https://api.heigit.org/openrouteservice/v2/directions/{PROFILE_MAP[profile]}/geojson',
             headers={'Authorization':ORS_KEY,'Content-Type':'application/json'},json=params,timeout=18.0)
        result.raise_for_status()
        feature=result.json()['features'][0]
        coords=feature['geometry']['coordinates']
        return {'points':[[p[1],p[0]] for p in coords],
                'distance_m':round(feature['properties']['summary']['distance']),
                'duration_s':round(feature['properties']['summary']['duration'])}
    except (httpx.HTTPError,KeyError,IndexError,TypeError,ValueError) as exc:
        raise RuntimeError(f'Routing provider unavailable or rejected route: {str(exc)[:150]}') from exc

def campus_demo(profile,reports):
    from importlib.util import spec_from_file_location,module_from_spec
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'data'/'legacy_routes.py'
    spec=spec_from_file_location('legacy_routes',path);mod=module_from_spec(spec);spec.loader.exec_module(mod)
    scored=[]
    for r in mod.ROUTES:
        points=[list(x) for x in r['points']]
        near=hazards_near(points,reports,profile,30)
        scored.append((len(near),len(points),r,points,near))
    _,_,choice,points,near=min(scored,key=lambda x:(x[0],x[1]))
    return {'mode':'demo','provider':'Illustrative campus polylines (NOT actual navigable directions)',
            'route':{'id':choice['id'],'points':points,'distance_m':round(sum(haversine(a,b) for a,b in zip(points,points[1:]))), 'duration_s':None},
            'baseline':{'points':[list(p) for p in mod.ROUTES[0]['points']]},
            'alerts':[{'id':r['id'],'category':r['category'],'source':r['source'],'description':r['description'],'distance_m':round(r['distance_m'])} for r in near[:12]],
            'changed':choice['id']!=mod.ROUTES[0]['id'], 'explanation':'Campus demonstration: selected a predefined illustrative line with fewer nearby reports. Actual path accessibility and connectivity have not been verified.',
            'caveat':'NOT NAVIGATION: lines are unsurveyed candidates. Do not rely on them for travel.'}

def find_route(start,end,profile):
    if profile not in PROFILE_MAP: raise HTTPException(422,'Unsupported mobility profile')
    for point in (start,end):
        if not (32.5<=point[0]<=33.2 and -117.6<=point[1]<=-116.6):
            raise HTTPException(422,'Select two locations within greater San Diego')
    reports=all_reports()
    if not ORS_KEY:
        raise HTTPException(503,'ORS_API_KEY not configured. Add an OpenRouteService API key for real pedestrian routing, or use Campus Demo.')
    try: baseline=ors_request(start,end,profile)
    except RuntimeError as exc: raise HTTPException(502,str(exc)) from exc
    alerts=hazards_near(baseline['points'],reports,profile,28)
    avoid=avoid_polygons(alerts,start,end)
    best=baseline;changed=False;warning=None
    if avoid:
        try:
            candidate=ors_request(start,end,profile,avoid)
            # Only use alternate if it reduces exposure, not merely produces a different line.
            candidate_alerts=hazards_near(candidate['points'],reports,profile,28)
            if len(candidate_alerts)<len(alerts): best=candidate;changed=True
            else: warning='No lower-report-exposure alternative found. Original route shown.'
        except RuntimeError:
            warning='Routing service could not calculate an avoidance route. Original route shown.'
    return {'mode':'live','provider':'OpenRouteService walking network',
        'route':{'id':'precautionary' if changed else 'baseline',**best},
        'baseline':baseline,'changed':changed,
        'alerts':[{'id':r['id'],'category':r['category'],'source':r['source'], 'description':r['description'],
                   'distance_m':round(r['distance_m'])} for r in alerts[:12]],
        'explanation':explain_route(profile,alerts,changed),
        'warning':warning,
        'caveat':'Community and City reports are unverified. Routes do not guarantee accessibility, working elevators, or safe passage. Use on-site judgment.'}
