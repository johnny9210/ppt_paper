"""Run new vocabulary-free metrics on 4 methods × 10 dark-glass designs.

Metrics:
  HTML/DOM-based (vocabulary-free):
    VEC, EDC, VLC, CRP, HD, SC, ZDX
  PNG-based (visual fidelity):
    CLIP, LPIPS  (SSIM removed — not informative for design2code; see paper)

Output:
  results/new_eval/dom_metrics.jsonl
  results/new_eval/visual_metrics.jsonl
  results/new_eval/summary.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from experiments.metrics.dom_structure import extract_dom_metrics

OUT = _ROOT / "results" / "new_eval"
OUT.mkdir(parents=True, exist_ok=True)

DARK_GLASS = [
    "design_01_timeline","design_02_dashboard","design_03_comparison_split",
    "design_04_pyramid","design_05_hub_spoke","design_06_before_after",
    "design_07_feature_grid","design_08_roadmap","design_09_layered_stack",
    "design_10_stats_hero",
]


def _load_all_designs() -> list[str]:
    """N=48 mixed: read all design IDs from slide_specs.jsonl."""
    specs_path = _ROOT / "data" / "slide_specs.jsonl"
    return [json.loads(l)["id"] for l in specs_path.read_text().splitlines() if l.strip()]

METHODS = {
    # Table 1: same-model GPT-4o comparison
    "single_pass":               "results/raw/single_pass",
    "visual_cot":                "results/raw/visual_cot",
    "cot_h_rag":                 "results/raw/cot_h_rag",
    "layeragent":                "results/raw/layeragent",
    # §6.7 ablation: D₄ no_designspec (H-AblationDesignSpec, Appendix A)
    "layeragent-no_designspec":  "results/raw/layeragent-no_designspec",
    # Table 2: cross-model cost-efficiency
    "single_pass_gpt_5_4":       "results/raw/single_pass_gpt_5_4",
    "single_pass_claude_4_6_opus": "results/raw/single_pass_claude_4_6_opus",
}


def run_dom_metrics():
    out_path = OUT / "dom_metrics.jsonl"
    print(f"\n=== DOM metrics → {out_path} ===")
    rows = []
    with out_path.open("w") as f:
        for method, raw_dir in METHODS.items():
            for did in DARK_GLASS:
                html = _ROOT / raw_dir / f"{did}_seed0.html"
                if not html.exists():
                    print(f"  miss {method}/{did}")
                    continue
                try:
                    m = extract_dom_metrics(html)
                except Exception as e:
                    print(f"  err {method}/{did}: {e}")
                    continue
                row = {"method": method, "design_id": did, **m}
                rows.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                print(f"  {method:<32} {did:<28} VEC={m['vec']:>3} EDC={m['edc']:>3} VLC={m['vlc']:>3} CRP={m['crp']:>4} HD={m['hd']:>2}")
    return rows


def run_visual_metrics():
    """CLIP + LPIPS vs reference PNG (SSIM excluded — see module docstring)."""
    from experiments.metrics.visual_similarity import all_visual_metrics
    out_path = OUT / "visual_metrics.jsonl"
    print(f"\n=== Visual metrics → {out_path} ===")
    rows = []
    SHOTS = _ROOT / "results" / "screenshots"
    REF_DIR = _ROOT / "data" / "eval_dataset" / "slides"

    with out_path.open("w") as f:
        for method in METHODS:
            method_dir = SHOTS / method
            for did in DARK_GLASS:
                ref = REF_DIR / f"{did}.png"
                # Try both naming conventions: with and without _seed0 suffix
                gen = method_dir / f"{did}_seed0.png"
                if not gen.exists():
                    gen = method_dir / f"{did}.png"
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
                print(f"  {method:<32} {did:<28} CLIP={m['clip']:.3f} LPIPS={m['lpips']:.3f} ({elapsed:.1f}s)")
    return rows


def aggregate(dom_rows, visual_rows):
    from collections import defaultdict
    from statistics import mean, stdev

    by = defaultdict(lambda: {"dom": [], "vis": []})
    for r in dom_rows:
        by[r["method"]]["dom"].append(r)
    for r in visual_rows:
        by[r["method"]]["vis"].append(r)

    print(f"\n=== Aggregate (N={len(DARK_GLASS)} dark-glass) ===")
    print(f"{'method':<32} {'VEC':>6} {'EDC':>6} {'VLC':>6} {'CRP':>6} {'HD':>4}  {'CLIP':>6} {'LPIPS':>6}")
    print('-' * 90)
    summary = {}
    for method in METHODS:
        d = by[method]
        if not d["dom"] or not d["vis"]:
            continue
        agg = {
            "n_dom": len(d["dom"]),
            "n_vis": len(d["vis"]),
            "vec": mean(r["vec"] for r in d["dom"]),
            "edc": mean(r["edc"] for r in d["dom"]),
            "vlc": mean(r["vlc"] for r in d["dom"]),
            "crp": mean(r["crp"] for r in d["dom"]),
            "hd":  mean(r["hd"]  for r in d["dom"]),
            "sc":  mean(r["sc"]  for r in d["dom"]),
            "zdx": mean(r["zdx"] for r in d["dom"]),
            "clip": mean(r["clip"] for r in d["vis"]),
            "lpips": mean(r["lpips"] for r in d["vis"]),
        }
        summary[method] = agg
        print(f"{method:<32} {agg['vec']:>6.1f} {agg['edc']:>6.1f} {agg['vlc']:>6.1f} {agg['crp']:>6.1f} "
              f"{agg['hd']:>4.1f}  {agg['clip']:>6.3f} {agg['lpips']:>6.3f}")

    out = OUT / "summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nsaved → {out}")
    return summary


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--skip-dom", action="store_true")
    p.add_argument("--skip-vis", action="store_true")
    p.add_argument("--all-designs", action="store_true",
                   help="N=48 mixed (default: N=10 dark-glass)")
    p.add_argument("--out-suffix", default="",
                   help="suffix for output files (e.g. '_n48')")
    args = p.parse_args()

    if args.all_designs:
        DARK_GLASS = _load_all_designs()
        print(f"[run_new_eval] mode=N={len(DARK_GLASS)} mixed")
        if args.out_suffix:
            OUT = _ROOT / "results" / f"new_eval{args.out_suffix}"
            OUT.mkdir(parents=True, exist_ok=True)

    dom_rows = []
    visual_rows = []

    if not args.skip_dom:
        dom_rows = run_dom_metrics()
    else:
        with (OUT / "dom_metrics.jsonl").open() as f:
            dom_rows = [json.loads(l) for l in f if l.strip()]

    if not args.skip_vis:
        visual_rows = run_visual_metrics()
    elif (OUT / "visual_metrics.jsonl").exists():
        with (OUT / "visual_metrics.jsonl").open() as f:
            visual_rows = [json.loads(l) for l in f if l.strip()]

    if dom_rows and visual_rows:
        aggregate(dom_rows, visual_rows)
