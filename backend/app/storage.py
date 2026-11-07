"""Local JSON/photo store: suitable for demo, not persistent cloud production."""
from __future__ import annotations
import io, json, os, threading, uuid
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError
from .config import DATA, PHOTOS
_LOCK = threading.RLock()
REPORTS = DATA / 'community_reports.json'
FEEDBACK = DATA / 'feedback.json'

def read_json(path: Path):
    if not path.exists(): return []
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list): raise ValueError(f'{path.name} must contain a JSON list')
    return data

def write_json(path: Path, rows: list):
    tmp = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(tmp, path)
    finally: tmp.unlink(missing_ok=True)

def get_community():
    with _LOCK: return read_json(REPORTS)

def store_image(content: bytes, report_id: str):
    if not content or len(content) > 8 * 1024 * 1024: raise ValueError('Photo must be smaller than 8 MB')
    try:
        with Image.open(io.BytesIO(content)) as im:
            if im.format not in {'JPEG', 'PNG', 'WEBP'}: raise ValueError('Upload JPG, PNG, or WEBP')
            im = ImageOps.exif_transpose(im)
            im.thumbnail((1400, 1400))
            if im.mode != 'RGB':
                rgba = im.convert('RGBA')
                canvas = Image.new('RGB', im.size, 'white')
                canvas.paste(rgba, mask=rgba.getchannel('A'))
                im = canvas
            path = PHOTOS / f'{report_id}.jpg'
            im.save(path, 'JPEG', optimize=True, quality=82)  # strips EXIF location
            return f'/photos/{report_id}.jpg'
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError('Unable to open photo') from exc

def create_report(*, lat, lng, category, description, profile_impacts, image=None, ai_status='manual', severity='unknown'):
    report_id = 'cp_' + uuid.uuid4().hex[:12]
    photo_url = store_image(image, report_id) if image else None
    row = {'id':report_id, 'lat':float(lat), 'lng':float(lng), 'category':category,
           'description':description[:600], 'severity':severity, 'affects':profile_impacts,
           'source':'clearpath', 'source_label':'Community report · not independently verified',
           'verified':False, 'ai_status':ai_status, 'photo_url':photo_url,
           'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds')}
    with _LOCK:
        rows=read_json(REPORTS); rows.append(row); write_json(REPORTS,rows)
    return row

def save_feedback(route_id:str, profile:str, helpful:bool):
    row={'route_id':route_id,'profile':profile,'helpful':helpful,'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds')}
    with _LOCK:
        rows=read_json(FEEDBACK); rows.append(row); write_json(FEEDBACK,rows)
    return row
