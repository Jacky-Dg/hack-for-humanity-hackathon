import io
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app import storage
from app.routing import distance_to_polyline, hazards_near, campus_demo

client = TestClient(app)

def test_health_and_city_records():
    response=client.get('/api/health')
    assert response.status_code==200
    assert response.json()['city_reports']>100
    rows=client.get('/api/reports',params={'south':32.86,'west':-117.26,'north':32.91,'east':-117.21,'profile':'wheelchair'}).json()['reports']
    assert isinstance(rows,list)
    assert all('category' in r and 'source' in r for r in rows)

def test_clustering():
    response=client.get('/api/clusters',params={'south':32.86,'west':-117.26,'north':32.91,'east':-117.21})
    assert response.status_code==200
    assert isinstance(response.json()['clusters'],list)

def test_campus_demo_distinct_from_verified_navigation():
    res=client.post('/api/route',json={'start':{'lat':32.87965,'lng':-117.23758},'destination':{'lat':32.88072,'lng':-117.23763},'profile':'wheelchair','demo':True})
    assert res.status_code==200
    data=res.json()
    assert data['mode']=='demo'
    assert 'NOT NAVIGATION' in data['caveat']
    assert len(data['route']['points'])>=2

def test_distance_and_hazard_filter():
    route=[[32.88,-117.24],[32.881,-117.24]]
    assert distance_to_polyline([32.8805,-117.24],route)<1
    candidate={'id':'test','lat':32.8805,'lng':-117.24,'affects':{'wheelchair':True},'source':'clearpath'}
    assert len(hazards_near(route,[candidate],'wheelchair'))==1
    assert len(hazards_near(route,[candidate],'low_vision'))==0

def test_text_submission_and_image_sanitize(monkeypatch,tmp_path):
    monkeypatch.setattr(storage,'REPORTS',tmp_path/'reports.json')
    monkeypatch.setattr(storage,'PHOTOS',tmp_path/'photos')
    storage.PHOTOS.mkdir()
    # No Gemini key: report stays unverified with unknown severity.
    res=client.post('/api/reports',data={'lat':'32.881','lng':'-117.237','category':'sidewalk','description':'Uneven pavement near path'})
    assert res.status_code==200,res.text
    report=res.json()
    assert report['source']=='clearpath' and report['verified'] is False
    assert report['severity']=='unknown'
    assert len(storage.get_community())==1
    buff=io.BytesIO()
    Image.new('RGB',(64,64),'gray').save(buff,format='PNG')
    saved=storage.create_report(lat=32.88,lng=-117.23,category='debris',description='Possible debris',profile_impacts={'wheelchair':True},image=buff.getvalue())
    assert saved['photo_url'].endswith('.jpg')
    assert (storage.PHOTOS / Path(saved['photo_url']).name).is_file()

def test_no_demo_location_from_backend():
    response=client.post('/api/reports',data={'lat':'0','lng':'0','description':'test'})
    assert response.status_code==422
