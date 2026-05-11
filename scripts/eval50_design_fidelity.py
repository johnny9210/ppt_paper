"""Run the SOTA design-fidelity metric pack on 4 methods × 50 slides.

Outputs:
  results/eval50_v4_logs/design_fidelity_rows.jsonl  — one row per cell
  results/eval50_v4_logs/summary.json                 — per-method aggregates
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REF_DIR = ROOT / "data" / "eval_dataset" / "slides"
RAW = ROOT / "results" / "raw"
SHOTS = ROOT / "results" / "screenshots"
LOG_DIR = ROOT / "results" / "eval50_v4_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

METHODS = ["layeragent_v4", "single_pass", "visual_cot", "cot_h_rag"]


def list_slides() -> list[str]:
    return sorted(p.stem for p in REF_DIR.glob("*.png"))


def main():
    from experiments.metrics.design_fidelity import all_design_metrics

    slides = list_slides()
    print(f"[eval50] {len(METHODS)} methods × {len(slides)} slides = {len(METHODS) * len(slides)} cells")

    rows: list[dict] = []
    out_jsonl = LOG_DIR / "design_fidelity_rows.jsonl"
    with out_jsonl.open("w") as f:
        for sid in slides:
            ref = REF_DIR / f"{sid}.png"
            if not ref.exists():
                print(f"  ! ref missing: {sid}")
                continue
            for method in METHODS:
                html = RAW / method / f"{sid}_seed0.html"
                png = SHOTS / method / f"{sid}.png"
                if not (html.exists() and png.exists()):
                    print(f"  ~ skip {method}/{sid}")
                    continue
                t0 = time.time()
                try:
                    m = all_design_metrics(ref, html, png, skip_judge=False)
                    m["method"] = method
                    m["slide"] = sid
                    m["_elapsed_s"] = round(time.time() - t0, 1)
                    rows.append(m)
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")
                    f.flush()
                    print(f"  {method:<14} / {sid:<55}  "
                          f"BM={m.get('block_match_f1',0):.2f} "
                          f"Eluo={m.get('element_iou',0):.2f} "
                          f"WS={m.get('whitespace_frac',0):.2f} "
                          f"Lo={m.get('layout_0_5','?')} Co={m.get('color_0_5','?')} "
                          f"({m['_elapsed_s']:.1f}s)")
                except Exception as e:
                    print(f"  ✗ {method}/{sid}: {type(e).__name__}: {e}")

    # Aggregate
    keys_higher = ["block_match_f1", "element_iou", "layout_0_5", "color_0_5"]
    keys_lower = ["color_ciede2000", "whitespace_frac", "collision_score"]

    def safe(v):
        import math
        return v if isinstance(v, (int, float)) and not math.isnan(v) else None

    agg = {}
    for method in METHODS:
        method_rows = [r for r in rows if r["method"] == method]
        agg[method] = {"n": len(method_rows)}
        for k in keys_higher + keys_lower:
            vals = [safe(r.get(k)) for r in method_rows]
            vals = [v for v in vals if v is not None]
            agg[method][k] = mean(vals) if vals else float("nan")

    print("\n=== Aggregate (mean across slides per method) ===")
    hdr = (f"{'method':<16} {'n':>3} {'BM↑':>5} {'EIoU↑':>5} {'ΔE↓':>5} | "
           f"{'WS↓':>5} {'COL↓':>5} | {'Lo':>4} {'Co':>4}")
    print(hdr)
    print("-" * len(hdr))
    for method in METHODS:
        a = agg[method]
        print(f"{method:<16} {a['n']:>3} "
              f"{a['block_match_f1']:>5.3f} {a['element_iou']:>5.3f} {a['color_ciede2000']:>5.1f} | "
              f"{a['whitespace_frac']:>5.2f} {a['collision_score']:>5.2f} | "
              f"{a['layout_0_5']:>4.1f} {a['color_0_5']:>4.1f}")

    # Per-slide z-score composite, averaged per method
    method_zs: dict[str, list[float]] = {m: [] for m in METHODS}
    for sid in slides:
        for k in keys_higher:
            vals = [safe(next((r.get(k) for r in rows if r["method"] == m and r["slide"] == sid), None))
                    for m in METHODS]
            clean = [v for v in vals if v is not None]
            if not clean:
                continue
            mu = sum(clean) / len(clean)
            sd = (sum((x - mu) ** 2 for x in clean) / len(clean)) ** 0.5 or 1.0
            for mm, v in zip(METHODS, vals):
                if v is not None:
                    method_zs[mm].append((v - mu) / sd)
        for k in keys_lower:
            vals = [safe(next((r.get(k) for r in rows if r["method"] == m and r["slide"] == sid), None))
                    for m in METHODS]
            clean = [v for v in vals if v is not None]
            if not clean:
                continue
            mu = sum(clean) / len(clean)
            sd = (sum((x - mu) ** 2 for x in clean) / len(clean)) ** 0.5 or 1.0
            for mm, v in zip(METHODS, vals):
                if v is not None:
                    method_zs[mm].append(-(v - mu) / sd)  # invert for lower-is-better

    print("\n=== Composite ranking (mean z-score, higher = closer to reference) ===")
    composite = sorted(((m, (mean(zs) if zs else 0.0)) for m, zs in method_zs.items()),
                       key=lambda x: -x[1])
    for m, z in composite:
        print(f"  {m:<16} z = {z:+.3f}")

    summary = {
        "n_slides": len(slides),
        "agg_means": agg,
        "composite_z": dict(composite),
    }
    summary_path = LOG_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nsummary → {summary_path}")


if __name__ == "__main__":
    main()
