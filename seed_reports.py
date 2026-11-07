"""Import actual campus photos from seed_manifest.csv; safe to rerun (IDs stable)."""
import csv
import hashlib
from pathlib import Path

from backend import load_reports, save_report

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "seed_manifest.csv"


def as_bool(value):
    return str(value).strip().lower() in ("true", "1", "yes", "y")


def main():
    if not MANIFEST.exists():
        raise SystemExit("Create seed_manifest.csv first; see seed_manifest.example.csv")
    existing_ids = {r["id"] for r in load_reports()}
    with MANIFEST.open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            raw_path = row["photo_path"].strip()
            if not raw_path:
                continue
            src = (ROOT / raw_path).resolve()
            if not src.is_relative_to(ROOT / "photos") or not src.is_file():
                print(f"SKIP missing / invalid photo path: {raw_path}")
                continue
            report_id = "seed_" + hashlib.sha1(raw_path.encode()).hexdigest()[:12]
            if report_id in existing_ids:
                print(f"SKIP already imported: {raw_path}")
                continue
            analysis = {
                "is_obstacle": True,
                "type": row["type"],
                "severity": row["severity"],
                "affects": {
                    "wheelchair": as_bool(row["wheelchair"]),
                    "walking_aid": as_bool(row.get("walking_aid", True)),
                },
                "explanation": row["explanation"],
            }
            try:
                # For seeding, humans label the images. Only label observed obstacles.
                saved = save_report(src, row["lat"], row["lng"], analysis, report_id=report_id)
                existing_ids.add(report_id)
                print(f"OK {saved['id']}: {raw_path}")
            except (OSError, ValueError) as exc:
                print(f"ERROR {raw_path}: {exc}")


if __name__ == "__main__":
    main()
