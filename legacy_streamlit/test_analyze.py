"""Run analyze_photo on every photo in test_photos/ and print a one-line table.

    python test_analyze.py
"""
from pathlib import Path

from analyze import analyze_photo

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
photos = sorted(p for p in (Path(__file__).parent / "test_photos").iterdir() if p.suffix.lower() in EXTS)

print(f"{'filename':<28} | {'obst':<5} | {'type':<15} | {'severity':<10} | {'wc':<5} | {'cane':<5} | explanation")
print("-" * 120)
for p in photos:
    r = analyze_photo(p.read_bytes())
    if r is None:
        print(f"{p.name:<28} | FAILED (returned None)")
        continue
    a = r["affects"]
    print(f"{p.name:<28} | {str(r['is_obstacle']):<5} | {r['type']:<15} | {r['severity']:<10} | "
          f"{str(a['wheelchair']):<5} | {str(a['cane_walker']):<5} | {r['explanation']}")
