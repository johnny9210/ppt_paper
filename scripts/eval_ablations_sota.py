"""Measure SOTA design2code pack on D₂ / D₄ ablation outputs.

Outputs per cell:
  - element_iou
  - color_ciede2000
  - layout_0_5, color_0_5 (AutoPresent rubric, GPT-4o judge)

Result:
  results/eval50_v4_logs/ablation_sota_rows.jsonl
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.metrics.design_fidelity import all_design_metrics

REF_DIR = ROOT / "data" / "eval_dataset" / "slides"
LOG_DIR = ROOT / "results" / "eval50_v4_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
OUT = LOG_DIR / "ablation_sota_rows.jsonl"

CELLS = [
    ("D", "layeragent_v4"),
    ("D2", "layeragent_v4-no_text_inserter"),
    ("D4", "layeragent_v4-no_designspec"),
]


def list_slides() -> list[str]:
    return sorted(p.stem for p in REF_DIR.glob("*.png"))


def main():
    slides = list_slides()
    print(f"[ablation-sota] {len(CELLS)} variants × {len(slides)} slides = {len(CELLS) * len(slides)} cells")
    existing = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    d = json.loads(line)
                    existing.add((d.get("variant"), d.get("slide")))
                except Exception:
                    pass

    rows = []
    with OUT.open("a") as f:
        for variant_tag, dir_name in CELLS:
            raw_dir = ROOT / "results" / "raw" / dir_name
            shots_dir = ROOT / "results" / "screenshots" / dir_name
            for sid in slides:
                if (variant_tag, sid) in existing:
                    continue
                ref = REF_DIR / f"{sid}.png"
                html = raw_dir / f"{sid}_seed0.html"
                png = shots_dir / f"{sid}.png"
                if not (ref.exists() and html.exists() and png.exists()):
                    print(f"  ~ skip {variant_tag}/{sid}: ref={ref.exists()} html={html.exists()} png={png.exists()}")
                    continue
                t0 = time.time()
                try:
                    m = all_design_metrics(ref, html, png, skip_judge=False)
                    m["variant"] = variant_tag
                    m["slide"] = sid
                    m["_elapsed_s"] = round(time.time() - t0, 1)
                    rows.append(m)
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")
                    f.flush()
                    print(f"  {variant_tag:<3} / {sid:<55}  "
                          f"Eluo={m.get('element_iou',0):.2f} "
                          f"ΔE={m.get('color_ciede2000',0):.1f} "
                          f"Lo={m.get('layout_0_5','?')} Co={m.get('color_0_5','?')} "
                          f"({m['_elapsed_s']:.1f}s)")
                except Exception as e:
                    print(f"  ✗ {variant_tag}/{sid}: {type(e).__name__}: {e}")

    # Aggregate
    print("\n=== Aggregate (mean across 50 slides per variant) ===")
    print(f"{'variant':<6} {'Eluo↑':>6} {'ΔE↓':>6} {'Lo↑':>5} {'Co↑':>5} {'n':>4}")
    print("-" * 40)
    for variant_tag, _ in CELLS:
        sub = [r for r in rows if r.get("variant") == variant_tag and "_error" not in r]
        if not sub:
            print(f"{variant_tag:<6} (no rows)")
            continue
        def safe(k):
            vs = [r.get(k) for r in sub if isinstance(r.get(k), (int, float))]
            return mean(vs) if vs else float("nan")
        print(f"{variant_tag:<6} {safe('element_iou'):>6.3f} {safe('color_ciede2000'):>6.1f} "
              f"{safe('layout_0_5'):>5.2f} {safe('color_0_5'):>5.2f} {len(sub):>4}")

    print(f"\nsaved → {OUT}")


if __name__ == "__main__":
    main()
