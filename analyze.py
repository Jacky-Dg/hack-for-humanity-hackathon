"""ClearPath: photo -> accessibility-obstacle JSON via Gemini.

    python analyze.py photos/*.jpg

analyze_photo(image_bytes) -> dict | None   (None = Gemini/parse failure)
"""
import io
import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Literal

from google import genai
from google.genai import types
from PIL import Image, ImageOps
from pydantic import BaseModel

try:  # iPhone photos are HEIC; without this Pillow can't open them
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

MODEL = "gemini-3.5-flash"
FALLBACK_MODEL = "gemini-3.1-flash-lite"  # used for the retry (Gemini 503/504s under load)
TIMEOUT_MS = 20_000


class Affects(BaseModel):
    wheelchair: bool
    walking_aid: bool


class PhotoAnalysis(BaseModel):
    is_obstacle: bool
    type: Literal["broken_elevator", "blocked_ramp", "construction", "stairs", "steep_slope", "debris", "other"]
    severity: Literal["impassable", "difficult", "minor"]
    affects: Affects
    explanation: str


SYSTEM_PROMPT = """\
You review photos that people submit to ClearPath, a live accessibility map of the
UC San Diego campus. Decide whether the photo shows an obstacle for wheelchair users
or people who walk with a cane, walker, or crutches. Use ADA standards.

STEP 1: is_obstacle
Set is_obstacle=false if the photo is not of a campus path, building entrance,
elevator, or ramp (selfie, food, pet, screenshot, indoor room with nothing wrong), if
it is too blurry or dark to judge, or if the path is clear and usable. Normal wear,
hairline cracks, shadows, and objects kept out of the path are not obstacles.
If is_obstacle=false, set type="other", severity="minor",
affects={"wheelchair": false, "walking_aid": false}, and say why in explanation.

STEP 2: type (pick the main problem)
- broken_elevator: out-of-order sign, closed or taped-off doors, a dark or
  unresponsive elevator or call panel.
- blocked_ramp: something on or in front of a ramp or curb cut (bikes, scooters,
  carts, signs, parked cars), or a curb ramp that is missing or broken.
- construction: fencing, barriers, closures, detour signs, trenches, equipment.
- stairs: stairs or a step that is the only way through, with no ramp in view.
- steep_slope: a path or ramp that looks steeper than ADA allows (about 1:12 for
  ramps, about 1:20 for walkways), or a strong cross-slope.
- debris: loose gravel, branches, trash, spills, broken pavement, or uplifted
  slabs on the path.
- other: a real obstacle that fits none of the above (narrow path, door that
  can't be reached, missing handrail). Describe it in explanation.

STEP 3: severity (for whichever affected group it is WORST for, usually the wheelchair user)
- impassable: they cannot get through: an elevator that is the only route, stairs
  with no ramp (for a wheelchair), a fully blocked ramp or path, a construction closure.
- difficult: they can get through with a risk or a detour: partly blocked (less
  than about 36 inches clear), a steep slope, a crack or uplift of about 1/2 inch
  or more, a lot of debris.
- minor: small inconvenience, little risk.

STEP 4: affects
- wheelchair: true for anything that blocks or narrows a smooth, level, firm path,
  including stairs, slopes, uplifts, blockages, broken elevators, and debris that
  wheels can't roll over.
- walking_aid: true for people who walk with a cane, walker, or crutches. Mark it
  for trip and fall hazards (uplift, cracks, debris, loose gravel, wet or slippery
  ground), stairs (especially without a handrail), steep slopes, broken elevators
  (they would have to take the stairs), long detours, and uneven or soft ground.
  Usually false for a narrow gap that a person on foot can easily get through,
  or for a curb ramp that's blocked when a low curb next to it is easy to step.

explanation: one short sentence saying what you see and why it matters.
"""

_client = None


def _api_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    secrets = Path(__file__).parent / ".streamlit" / "secrets.toml"
    if secrets.exists():
        key = tomllib.loads(secrets.read_text()).get("GEMINI_API_KEY")
        if key:
            return key
    import streamlit as st  # Streamlit Community Cloud
    return st.secrets["GEMINI_API_KEY"]


def _client_():
    global _client
    if _client is None:
        _client = genai.Client(api_key=_api_key(), http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    return _client


def _prep(image_bytes):
    """Fix phone rotation, convert to RGB JPEG, shrink to <=1600px (faster, cheaper)."""
    if hasattr(image_bytes, "getvalue"):  # Streamlit UploadedFile
        image_bytes = image_bytes.getvalue()
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("RGB")
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def analyze_photo(image_bytes):
    try:
        jpeg = _prep(image_bytes)
    except Exception as e:
        print(f"analyze_photo: unreadable image: {e}", file=sys.stderr)
        return None

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=PhotoAnalysis,
        temperature=0.1,
    )
    contents = [types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"), "Analyze this photo."]

    for attempt, model in enumerate([MODEL, FALLBACK_MODEL]):  # one retry, on the fallback model
        try:
            resp = _client_().models.generate_content(model=model, contents=contents, config=config)
            result = PhotoAnalysis.model_validate(json.loads(resp.text))
            result.explanation = result.explanation.strip()
            if not result.explanation:  # backend rejects empty explanations
                raise ValueError("empty explanation")
            if not result.is_obstacle:  # keep non-obstacles uniform for the app
                result.type, result.severity = "other", "minor"
                result.affects = Affects(wheelchair=False, walking_aid=False)
            return result.model_dump()
        except Exception as e:
            print(f"analyze_photo attempt {attempt + 1} ({model}) failed: {str(e)[:200]}", file=sys.stderr)
    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for path in sys.argv[1:]:
        print(f"--- {path}")
        print(json.dumps(analyze_photo(Path(path).read_bytes()), indent=2))
