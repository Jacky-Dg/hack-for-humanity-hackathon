"""Gemini classifies submitted photos and optionally explains deterministic routing."""
from __future__ import annotations
import io
from PIL import Image, ImageOps
from pydantic import BaseModel, Field
from .config import GEMINI_KEY, GEMINI_MODEL
PROFILES=('wheelchair','cane','crutches','low_vision')
class Impact(BaseModel):
    wheelchair: bool = False
    cane: bool = False
    crutches: bool = False
    low_vision: bool = False
class ObstacleAssessment(BaseModel):
    is_obstacle: bool
    category: str = Field(description='one of sidewalk, ramp, elevator, construction, debris, lighting, stairs, slope, safety_concern, other')
    severity: str = Field(description='impassable, difficult, minor, or unknown')
    affects: Impact
    explanation: str = Field(max_length=360)
INSTRUCTIONS='''You assist ClearPath, a San Diego mobility accessibility reporting tool.
Assess only visible pedestrian or mobility obstacles and the submitter's description; community submissions are NOT verified field inspections.
Never infer exact ADA measurements, confirm a broken elevator without evidence, or claim any route is safe.
If image is blurry or irrelevant and description gives no evidence, set is_obstacle false.
Use severity unknown whenever uncertain. Do not identify people in images or infer personal characteristics.
Use category from specified set. Reply in structured JSON with short factual explanation.'''

_CLIENT = None
FALLBACK_MODEL = 'gemini-3.1-flash-lite'  # used when the main model is overloaded/out of quota

def _client():
    # Keep ONE client alive: a throwaway client gets garbage-collected mid-request
    # ("Cannot send a request, as the client has been closed").
    global _CLIENT
    if _CLIENT is None:
        from google import genai
        from google.genai import types
        _CLIENT = genai.Client(api_key=GEMINI_KEY, http_options=types.HttpOptions(timeout=20_000))
    return _CLIENT

def _generate(**kwargs):
    """Try the main model, then the fallback once (Gemini often returns 503/504/429 under load)."""
    try:
        return _client().models.generate_content(model=GEMINI_MODEL, **kwargs)
    except Exception:
        if GEMINI_MODEL == FALLBACK_MODEL:
            raise
        return _client().models.generate_content(model=FALLBACK_MODEL, **kwargs)

def inspect_photo(image_bytes:bytes, description:str)->dict:
    if not GEMINI_KEY: raise RuntimeError('Gemini API key not configured')
    from google.genai import types
    img=ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert('RGB')
    img.thumbnail((1400,1400)); buffer=io.BytesIO(); img.save(buffer,'JPEG',quality=80)
    res=_generate(
        contents=[types.Part.from_bytes(data=buffer.getvalue(),mime_type='image/jpeg'),f'Resident note: {description[:600] or "None"}'],
        config=types.GenerateContentConfig(system_instruction=INSTRUCTIONS,response_mime_type='application/json',
            response_schema=ObstacleAssessment,temperature=0.1))
    if not res.text: raise RuntimeError('Gemini returned no classification')
    result=ObstacleAssessment.model_validate_json(res.text).model_dump()
    if result['category'] not in {'sidewalk','ramp','elevator','construction','debris','lighting','stairs','slope','safety_concern','other'}: result['category']='other'
    if result['severity'] not in {'impassable','difficult','minor','unknown'}: result['severity']='unknown'
    return result

def explain_route(profile:str,alerts:list[dict],changed:bool)->str:
    if not alerts: return 'No nearby reports found along the initial route. This does not establish that the path is accessible.'
    basic=f'{len(alerts)} reported concerns near the initial route. ' + ('A precautionary detour was returned. ' if changed else 'No alternative route was returned. ') + 'Reports are unverified; verify conditions on site.'
    if not GEMINI_KEY: return basic
    try:
        from google.genai import types
        facts=[{'category':a['category'],'source':a['source'],'distance_m':round(a['distance_m'])} for a in alerts[:6]]
        res=_generate(
            contents=f'Profile={profile}, detour={changed}, reported concerns={facts}. In two short sentences explain the decision without suggesting any path is verified safe or the reports prove closures.',
            config=types.GenerateContentConfig(temperature=0.1,max_output_tokens=1024))
        return res.text.strip() if res.text else basic
    except Exception: return basic
