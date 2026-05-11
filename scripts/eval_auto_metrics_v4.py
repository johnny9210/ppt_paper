"""Re-measure auto metrics (DOM + visual similarity) on LayerAgent v4 outputs.

Reads LayerAgent HTML/PNG from results/raw/layeragent_v4/ + screenshots/layeragent_v4/
and computes VEC/EDC/VLC/CRP/HD/SC/ZDX + CLIP/LPIPS. Keeps baseline measurements
intact by sourcing them from existing v3 paths (single_pass / visual_cot / cot_h_rag).

Outputs:
  results/new_eval_v4/dom_metrics.jsonl    — DOM metrics, all 4 methods × 50 slides
  results/new_eval_v4/visual_metrics.jsonl — CLIP/LPIPS, all 4 methods × 50 slides
  results/new_eval_v4/summary.json         — per-method aggregate
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from experiments.metrics.dom_structure import extract_dom_metrics

OUT = _ROOT / "results" / "new_eval_v4"
OUT.mkdir(parents=True, exist_ok=True)

# LayerAgent reroutes to v4 outputs; baselines reuse existing data
METHODS = {
    "single_pass": "results/raw/single_pass",
    "visual_cot":  "results/raw/visual_cot",
    "cot_h_rag":   "results/raw/cot_h_rag",
    "layeragent":  "results/raw/layeragent_v4",   # ← swap target
}

SHOTS_DIR = {
    "single_pass": "results/screenshots/single_pass",
    "visual_cot":  "results/screenshots/visual_cot",
    "cot_h_rag":   "results/screenshots/cot_h_rag",
    "layeragent":  "results/screenshots/layeragent_v4",
}


def list_slides() -> list[str]:
    return sorted(p.stem for p in (_ROOT / "data" / "eval_dataset" / "slides").glob("*.png"))


def run_dom_metrics(slides: list[str]) -> list[dict]:
    out_path = OUT / "dom_metrics.jsonl"
    rows = []
    print(f"\n=== DOM metrics ({len(METHODS)} methods × {len(slides)} slides) → {out_path} ===")
    with out_path.open("w") as f:
        for method, raw_dir in METHODS.items():
            for did in slides:
                html = _ROOT / raw_dir / f"{did}_seed0.html"
                if not html.exists():
                    print(f"  miss {method}/{did}")
                    continue
                try:
                    m = extract_dom_metrics(html)
                except Exception as e:
                    print(f"  err {method}/{did}: {type(e).__name__}: {e}")
                    continue
                row = {"method": method, "design_id": did, **m}
                rows.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                print(f"  {method:<14} {did:<55} VEC={m['vec']:>3} EDC={m['edc']:>3} VLC={m['vlc']:>3} CRP={m['crp']:>4} HD={m['hd']:>2}")
    return rows


def run_visual_metrics(slides: list[str]) -> list[dict]:
    from experiments.metrics.visual_similarity import all_visual_metrics
    out_path = OUT / "visual_metrics.jsonl"
    rows = []
    print(f"\n=== Visual metrics → {out_path} ===")
    REF_DIR = _ROOT / "data" / "eval_dataset" / "slides"
    with out_path.open("w") as f:
        for method, shots in SHOTS_DIR.items():
            for did in slides:
                ref = REF_DIR / f"{did}.png"
                gen = _ROOT / shots / f"{did}.png"
                if not (ref.exists() and gen.exists()):
                    print(f"  miss {method}/{did}: ref={ref.exists()} gen={gen.exists()}")
                    continue
                try:
                    t0 = time.time()
                    m = all_visual_metrics(ref, gen)
                    elapsed = time.time() - t0
                except Exception as e:
                    print(f"  err {method}/{did}: {type(e).__name__}: {e}")
                    continue
                row = {"method": method, "design_id": did, **m, "_elapsed_s": elapsed}
                rows.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                print(f"  {method:<14} {did:<55} CLIP={m['clip']:.3f} LPIPS={m['lpips']:.3f} ({elapsed:.1f}s)")
    return rows


DARK_GLASS = {f"design_{i:02d}_{n}" for i, n in [
    (1, "timeline"), (2, "dashboard"), (3, "comparison_split"), (4, "pyramid"),
    (5, "hub_spoke"), (6, "before_after"), (7, "feature_grid"), (8, "roadmap"),
    (9, "layered_stack"), (10, "stats_hero")]}


def aggregate(dom_rows: list[dict], vis_rows: list[dict]) -> dict:
    """Aggregate full N=50 and N=10 dark_glass subset."""
    def agg(rows_dom, rows_vis):
        d = defaultdict(lambda: {"dom": [], "vis": []})
        for r in rows_dom: d[r["method"]]["dom"].append(r)
        for r in rows_vis: d[r["method"]]["vis"].append(r)
        out = {}
        for method, x in d.items():
            if not (x["dom"] and x["vis"]):
                continue
            out[method] = {
                "n_dom": len(x["dom"]), "n_vis": len(x["vis"]),
                "vec": mean(r["vec"] for r in x["dom"]),
                "edc": mean(r["edc"] for r in x["dom"]),
                "vlc": mean(r["vlc"] for r in x["dom"]),
                "crp": mean(r["crp"] for r in x["dom"]),
                "hd":  mean(r["hd"]  for r in x["dom"]),
                "sc":  mean(r["sc"]  for r in x["dom"]),
                "clip": mean(r["clip"] for r in x["vis"]),
                "lpips": mean(r["lpips"] for r in x["vis"]),
            }
        return out

    full = agg(dom_rows, vis_rows)
    dg_dom = [r for r in dom_rows if r["design_id"] in DARK_GLASS]
    dg_vis = [r for r in vis_rows if r["design_id"] in DARK_GLASS]
    dark = agg(dg_dom, dg_vis)

    summary = {"full_N50": full, "dark_glass_N10": dark}

    print("\n=== Full N=50 aggregate ===")
    hdr = f"{'method':<14} {'VEC':>6} {'EDC':>6} {'VLC':>6} {'CRP':>6} {'HD':>4}  {'CLIP':>6} {'LPIPS':>6}"
    print(hdr); print("-" * len(hdr))
    for m in ["single_pass", "visual_cot", "cot_h_rag", "layeragent"]:
        a = full.get(m)
        if a:
            print(f"{m:<14} {a['vec']:>6.1f} {a['edc']:>6.1f} {a['vlc']:>6.2f} {a['crp']:>6.1f} {a['hd']:>4.1f}  {a['clip']:>6.3f} {a['lpips']:>6.3f}")

    print("\n=== Dark-glass N=10 subset ===")
    print(hdr); print("-" * len(hdr))
    for m in ["single_pass", "visual_cot", "cot_h_rag", "layeragent"]:
        a = dark.get(m)
        if a:
            print(f"{m:<14} {a['vec']:>6.1f} {a['edc']:>6.1f} {a['vlc']:>6.2f} {a['crp']:>6.1f} {a['hd']:>4.1f}  {a['clip']:>6.3f} {a['lpips']:>6.3f}")

    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nsaved → {OUT / 'summary.json'}")
    return summary


def main():
    slides = list_slides()
    print(f"[v4-auto-eval] {len(slides)} slides total")
    dom_rows = run_dom_metrics(slides)
    vis_rows = run_visual_metrics(slides)
    aggregate(dom_rows, vis_rows)


if __name__ == "__main__":
    main()
