"""One-time conversion of San Diego Get It Done CSV into compact, privacy-limited map data.
Usage: python scripts/import_city.py /path/to/get_it_done_requests_open_datasd.csv
"""
import json, re, sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
PATTERN=r'sidewalk|walkway|pedestrian|crosswalk|curb|ramp|street.?light|vegetation|tree|debris|dumping|construction|road repair|pothole|traffic signal'
def classify(service,detail):
    s=f'{service} {detail}'.lower()
    if 'street light' in s or 'traffic signal' in s: return 'lighting', {'wheelchair':False,'cane':True,'crutches':True,'low_vision':True}
    if 'sidewalk' in s or 'crosswalk' in s: return 'sidewalk', dict.fromkeys(['wheelchair','cane','crutches','low_vision'],True)
    if 'ramp' in s or 'curb' in s: return 'ramp', {'wheelchair':True,'cane':True,'crutches':True,'low_vision':False}
    if 'vegetation' in s or 'tree' in s: return 'debris', dict.fromkeys(['wheelchair','cane','crutches','low_vision'],True)
    if 'construction' in s: return 'construction',dict.fromkeys(['wheelchair','cane','crutches','low_vision'],True)
    if 'dumping' in s or 'debris' in s: return 'debris',dict.fromkeys(['wheelchair','cane','crutches','low_vision'],True)
    return 'other',{'wheelchair':True,'cane':True,'crutches':True,'low_vision':False}
def run(path,limit=3000):
    cols=['service_request_id','service_request_parent_id','date_requested','service_name','service_name_detail','status','lat','lng','public_description']
    df=pd.read_csv(path,usecols=lambda c:c in cols,dtype={'service_request_id':'string','service_request_parent_id':'string'},low_memory=False)
    df['lat']=pd.to_numeric(df.lat,errors='coerce');df['lng']=pd.to_numeric(df.lng,errors='coerce')
    df=df[df.lat.between(32.53,33.15)&df.lng.between(-117.35,-116.88)&df.service_request_parent_id.isna()]
    category=df.service_name.fillna('')+' '+df.service_name_detail.fillna('')
    # Match both category and public description, but do not export raw free text (possible identifying info)
    match=category+' '+df.public_description.fillna('')
    df=df[match.str.contains(PATTERN,case=False,regex=True,na=False)]
    df=df.drop_duplicates('service_request_id').sort_values('date_requested',ascending=False)
    campus=df[df.lat.between(32.86,32.91)&df.lng.between(-117.26,-117.21)].head(350)
    df=pd.concat([campus,df.head(limit)]).drop_duplicates('service_request_id').head(limit+350)
    output=[]
    for row in df.to_dict('records'):
        cat,affects=classify(str(row.get('service_name') or ''),str(row.get('service_name_detail') or ''))
        detail=' · '.join(s for s in [str(row.get('service_name') or ''),str(row.get('service_name_detail') or '')] if s and s.lower()!='nan')
        output.append({'id':'gid_'+str(row['service_request_id']),'lat':float(row['lat']),'lng':float(row['lng']),
            'category':cat,'description':detail[:160],'severity':'unknown','affects':affects,'source':'get_it_done',
            'source_label':'City Get It Done · unverified resident service request','verified':False,'photo_url':None,
            'created_at':str(row.get('date_requested') or ''),'status':str(row.get('status') or 'Unknown'),
            'source_id':str(row['service_request_id']),
            'source_url':'https://data.sandiego.gov/datasets/get-it-done-reports/'})
    out=ROOT/'data'/'city_reports.json'
    out.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Wrote {len(output)} real unverified service requests to {out}')
if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Usage: python scripts/import_city.py /path/to/file.csv')
    run(Path(sys.argv[1]))
