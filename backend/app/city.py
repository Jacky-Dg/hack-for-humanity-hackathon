"""Get It Done service requests are unverified and distinct from community reports."""
import json, math
from functools import lru_cache
from .config import DATA
from .storage import get_community
CITY=DATA/'city_reports.json'
@lru_cache(maxsize=1)
def get_city(): return json.loads(CITY.read_text(encoding='utf-8')) if CITY.exists() else []
def all_reports(): return get_city()+get_community()
def affects_profile(report,profile): return profile=='standard' or bool(report.get('affects',{}).get(profile))
def viewport(reports,bbox=None,profile='standard',source='all',limit=2500):
    out=[]
    for r in reports:
        if source!='all' and r.get('source')!=source: continue
        if not affects_profile(r,profile): continue
        if bbox and not(bbox[0]<=r['lat']<=bbox[2] and bbox[1]<=r['lng']<=bbox[3]): continue
        out.append(r)
        if len(out)>=limit: break
    return out
