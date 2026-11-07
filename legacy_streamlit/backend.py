"""ClearPath hackathon backend: local JSON storage, photo storage, and feedback.

Public contract:
    load_reports() -> list[dict]
    save_report(photo, lat, lng, analysis, report_id=None) -> dict
    save_feedback(route_id, profile, rating) -> dict
    load_feedback() -> list[dict]
    popup_html(report) -> str   # ready for folium.Popup(...)

Designed for one Streamlit process and a single-day demo.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps, UnidentifiedImageError

BASE_DIR = Path(__file__).resolve().parent
REPORTS_FILE = BASE_DIR / "reports.json"
FEEDBACK_FILE = BASE_DIR / "feedback.json"
PHOTOS_DIR = BASE_DIR / "photos"
PHOTOS_DIR.mkdir(exist_ok=True)

TYPES = {"broken_elevator", "blocked_ramp", "construction", "stairs", "steep_slope", "debris", "other"}
SEVERITIES = {"impassable", "difficult", "minor"}
PROFILES = {"wheelchair", "low_vision"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
_LOCK = threading.RLock()


def _timestamp() -> str:
    return datetime.now(ZoneInfo("America/Los_Angeles")).isoformat(timespec="minutes")


def _load_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read {path.name}: {exc}") from exc
    if not isinstance(data, list):
        raise RuntimeError(f"{path.name} must contain a JSON array")
    return data


def _write_list(path: Path, rows: list[dict]) -> None:
    """Write entire JSON document atomically to avoid partial writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.stem}_", suffix=".tmp",
                                         delete=False) as temp:
            tmp_path = Path(temp.name)
            json.dump(rows, temp, indent=2, ensure_ascii=False)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def load_reports() -> list[dict]:
    with _LOCK:
        return _load_list(REPORTS_FILE)


def load_feedback() -> list[dict]:
    with _LOCK:
        return _load_list(FEEDBACK_FILE)


def _photo_bytes(photo) -> bytes:
    """Accept Streamlit UploadedFile, bytes, or a local photo Path."""
    if isinstance(photo, (str, Path)):
        data = Path(photo).read_bytes()
    elif isinstance(photo, (bytes, bytearray)):
        data = bytes(photo)
    elif hasattr(photo, "getvalue"):
        data = photo.getvalue()
    else:
        raise ValueError("photo must be an uploaded file, bytes, or local path")
    if not data:
        raise ValueError("Photo is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Photo is too large (maximum: 8 MB)")
    return data


def _normalized_jpeg(data: bytes) -> bytes:
    """Validate, resize, and remove EXIF/location metadata from photos."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Upload a JPG, PNG, or WEBP image")
            im = ImageOps.exif_transpose(im)
            im.thumbnail((1280, 1280))
            if im.mode != "RGB":
                # Convert transparent images to white background.
                if im.mode in ("RGBA", "LA") or "transparency" in im.info:
                    rgba = im.convert("RGBA")
                    bg = Image.new("RGB", rgba.size, "white")
                    bg.paste(rgba, mask=rgba.getchannel("A"))
                    im = bg
                else:
                    im = im.convert("RGB")
            output = io.BytesIO()
            im.save(output, "JPEG", quality=82, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Uploaded file is not a valid photo") from exc


def _bool_field(value, name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"affects.{name} must be true or false")


def _validate_analysis(analysis: dict) -> dict:
    if not isinstance(analysis, dict):
        raise ValueError("Gemini analysis must be a dictionary")
    if analysis.get("is_obstacle") is not True:
        raise ValueError("No accessibility obstacle detected: report not saved")
    obstacle_type = analysis.get("type")
    severity = analysis.get("severity")
    if obstacle_type not in TYPES:
        raise ValueError(f"Invalid obstacle type: {obstacle_type!r}")
    if severity not in SEVERITIES:
        raise ValueError(f"Invalid severity: {severity!r}")
    affects = analysis.get("affects")
    if not isinstance(affects, dict):
        raise ValueError("Missing affects object")
    explanation = analysis.get("explanation", "")
    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("Gemini explanation is missing")
    return {
        "is_obstacle": True,
        "type": obstacle_type,
        "severity": severity,
        "affects": {
            "wheelchair": _bool_field(affects.get("wheelchair"), "wheelchair"),
            "low_vision": _bool_field(affects.get("low_vision"), "low_vision"),
        },
        "explanation": explanation.strip()[:1200],
    }


def save_report(photo, lat: float, lng: float, analysis: dict,
                report_id: str | None = None) -> dict:
    """Save a verified obstacle report and photo once; return shared-schema dict.

    Example:
        report = save_report(uploaded_file, 32.881, -117.237, gemini_json)
    """
    clean_analysis = _validate_analysis(analysis)
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError) as exc:
        raise ValueError("Latitude and longitude must be numbers") from exc
    if not (math.isfinite(lat) and -90 <= lat <= 90 and
            math.isfinite(lng) and -180 <= lng <= 180):
        raise ValueError("Latitude or longitude out of range")
    if report_id is None:
        report_id = "r_" + uuid.uuid4().hex[:12]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", report_id):
        raise ValueError("Invalid report ID")

    jpeg = _normalized_jpeg(_photo_bytes(photo))
    image_path = PHOTOS_DIR / f"{report_id}.jpg"
    report = {
        "id": report_id,
        "lat": lat,
        "lng": lng,
        "photo_url": f"photos/{report_id}.jpg",
        **clean_analysis,
        "reported_at": _timestamp(),
    }

    with _LOCK:
        rows = _load_list(REPORTS_FILE)
        if any(row.get("id") == report_id for row in rows):
            raise ValueError(f"Report ID already exists: {report_id}")
        # Save photo first, then make it visible to map in reports.json.
        image_path.write_bytes(jpeg)
        try:
            rows.append(report)
            _write_list(REPORTS_FILE, rows)
        except Exception:
            image_path.unlink(missing_ok=True)
            raise
    return report


def save_feedback(route_id: str, profile: str, rating: int) -> dict:
    """Save one thumbs feedback event: 1 = up, 0 = down."""
    if not isinstance(route_id, str) or not route_id.strip():
        raise ValueError("Route ID is required")
    if profile not in PROFILES:
        raise ValueError("Profile must be wheelchair or low_vision")
    if type(rating) is not int or rating not in (0, 1):
        raise ValueError("Rating must be 0 (down) or 1 (up)")
    feedback = {
        "id": "f_" + uuid.uuid4().hex[:12],
        "route_id": route_id,
        "profile": profile,
        "rating": rating,
        "reported_at": _timestamp(),
    }
    with _LOCK:
        entries = _load_list(FEEDBACK_FILE)
        entries.append(feedback)
        _write_list(FEEDBACK_FILE, entries)
    return feedback


def popup_html(report: dict) -> str:
    """Generate a photo-proof Folium popup (embeds a small image, no server needed)."""
    severity = report.get("severity", "minor")
    color = {"impassable": "#dc2626", "difficult": "#ea580c", "minor": "#16a34a"}.get(severity, "#6b7280")
    image_html = ""
    photo_rel = report.get("photo_url", "")
    # Never use an arbitrary path from imported JSON to read outside photos/.
    if isinstance(photo_rel, str) and re.fullmatch(r"photos/[A-Za-z0-9_-]{1,50}\.jpg", photo_rel):
        path = BASE_DIR / photo_rel
        if path.is_file():
            with Image.open(path) as im:
                im.thumbnail((340, 220))
                out = io.BytesIO()
                im.convert("RGB").save(out, "JPEG", quality=66)
            encoded = base64.b64encode(out.getvalue()).decode("ascii")
            image_html = f'<img src="data:image/jpeg;base64,{encoded}" style="max-width:100%;border-radius:6px;margin:6px 0;" />'
    affected = ", ".join(k.replace("_", " ") for k, v in report.get("affects", {}).items() if v)
    return (
        '<div style="width:240px;font-family:sans-serif">'
        f'<strong>{escape(str(report.get("type", "other")).replace("_", " ").title())}</strong><br>'
        f'<span style="color:{color};font-weight:bold">{escape(str(severity).upper())}</span><br>'
        f'{image_html}'
        f'<div>{escape(str(report.get("explanation", "")))}</div>'
        f'<small>Affects: {escape(affected or "not specified")}</small>'
        '</div>'
    )
