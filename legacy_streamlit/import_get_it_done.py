"""Import a small *separate* City of San Diego Get It Done demo sample.

Run in ClearPath root:
    python import_get_it_done.py --download

Uses City-published open requests; these are unverified resident submissions.
Does NOT edit reports.json or the UCSD routing dataset.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

CSV_URL = "https://seshat.datasd.org/get_it_done_reports/get_it_done_requests_open_datasd.csv"
DATASET_URL = "https://data.sandiego.gov/datasets/get-it-done-reports/"
ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT / "get_it_done_requests_open_datasd.csv"
OUTPUT = ROOT / "get_it_done_demo.json"

# Potential pedestrian-access categories/description words, NOT proof of an obstacle.
PATTERN = re.compile(
    r"sidewalk|walkway|crosswalk|pedestrian|wheelchair|curb\s*ramp|"
    r"accessib|\bada\b|trip\s*hazard|blocked\s*(?:path|ramp)|"
    r"vegetation\s*encroachment|overgrown\s*(?:vegetation|bush|tree)|"
    r"obstruct(?:ed|ion|ing)?\s*(?:sidewalk|walkway|path|ramp)",
    re.IGNORECASE,
)


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine distance between two GPS points in km."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1, math.sqrt(a)))


def download_csv(destination: Path) -> None:
    print("Downloading City of San Diego open Get It Done requests (~30 MB)...")
    request = Request(CSV_URL, headers={"User-Agent": "ClearPath-hackathon-demo/1.0"})
    with urlopen(request, timeout=90) as response, destination.open("wb") as f:
        shutil.copyfileobj(response, f)
    print(f"Saved {destination.name}")


def parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def as_report(row: dict[str, str]) -> dict | None:
    """Convert a candidate to the shared front-end shape, with demo caveats."""
    rid = (row.get("service_request_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", rid):
        return None
    try:
        lat = float(row.get("lat", ""))
        lng = float(row.get("lng", ""))
    except (ValueError, TypeError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lng) and 32 <= lat <= 34 and -118 <= lng <= -116):
        return None

    service = (row.get("service_name") or "Other").strip()
    detail = (row.get("service_name_detail") or "").strip()
    status = (row.get("status") or "Unknown").strip()
    requested = (row.get("date_requested") or "").strip()
    label = ": ".join(x for x in (service, detail) if x)[:160]
    # Do not copy public free-text descriptions; they can contain personal details.
    # These classifications are placeholders for displaying unverified candidate reports.
    return {
        "id": f"gid_{rid}",
        "lat": lat,
        "lng": lng,
        "photo_url": "",  # City CSV does NOT supply photo proof.
        "is_obstacle": True,  # Demo candidate ONLY; NOT an independently verified obstacle.
        "type": "other",
        "severity": "minor",  # Schema requires a value. Actual severity is UNKNOWN.
        "affects": {"wheelchair": True, "low_vision": True},  # Potential; NOT assessed.
        "explanation": (
            f"City Get It Done report: {label}. Status: {status}. "
            "POTENTIAL pedestrian-access concern only — NOT photo-verified, "
            "NOT Gemini-assessed; severity and affected profiles are UNKNOWN."
        ),
        "reported_at": requested,
        "source": "City of San Diego Get It Done",
        "source_url": DATASET_URL,
        "source_id": rid,
        "source_status": status,
        "verified": False,
        "demo_unverified": True,
        "severity_unverified": True,
        "affects_unverified": True,
    }


def import_rows(csv_path: Path, *, center_lat: float, center_lng: float,
                radius_km: float, max_days: int, limit: int) -> list[dict]:
    cutoff = date.today() - timedelta(days=max_days)
    candidates: list[tuple[float, str, dict]] = []
    seen: set[str] = set()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"service_request_id", "lat", "lng", "service_name", "date_requested"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

        for row in reader:
            # Avoid counting city-designated duplicate reports as separate cases.
            if (row.get("service_request_parent_id") or "").strip():
                continue
            rid = (row.get("service_request_id") or "").strip()
            if not rid or rid in seen:
                continue
            category = " ".join((row.get("service_name") or "", row.get("service_name_detail") or ""))
            description = row.get("public_description") or ""
            if not PATTERN.search(category + " " + description):
                continue
            requested = parse_date(row.get("date_requested") or "")
            if requested is None or requested < cutoff:
                continue
            converted = as_report(row)
            if converted is None:
                continue
            distance = distance_km(center_lat, center_lng, converted["lat"], converted["lng"])
            if distance > radius_km:
                continue
            seen.add(rid)
            # Pick closest reports, then newest, for a focused La Jolla/UCSD vicinity demo.
            candidates.append((distance, requested.isoformat(), converted))

    candidates.sort(key=lambda x: (x[0], -date.fromisoformat(x[1]).toordinal()))
    return [r for _d, _date, r in candidates[:limit]]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Download City CSV first")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--center-lat", type=float, default=32.881)
    parser.add_argument("--center-lng", type=float, default=-117.237)
    parser.add_argument("--radius-km", type=float, default=6)
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)
    if args.download:
        download_csv(args.csv)
    if not args.csv.is_file():
        parser.error(f"Missing {args.csv}. Run with --download or download the CSV from {DATASET_URL}")
    if args.limit < 1 or args.days < 1 or args.radius_km <= 0:
        parser.error("limit, days, and radius-km must be positive")
    reports = import_rows(args.csv, center_lat=args.center_lat, center_lng=args.center_lng,
                          radius_km=args.radius_km, max_days=args.days, limit=args.limit)
    args.output.write_text(json.dumps(reports, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(reports)} source-labeled, UNVERIFIED reports to {args.output.name}")
    if not reports:
        print("No matching reports; try --radius-km 12 --days 1500")
    print("Your real reports.json and campus routing data are unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
