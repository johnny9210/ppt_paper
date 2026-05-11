"""Re-run the McKinsey 5-way comparison with the SOTA design-fidelity metric set.

Replaces SSIM/CLIP/LPIPS (blank-canvas-attack vulnerable) with:
  - Block-Match F1, Element-IoU (Hungarian), CIEDE2000 color distance
  - AeSlides Whitespace + Collision (deterministic, blank-canvas penalty)
  - AutoPresent Layout/Color GPT-4o judge (0-5)

The latest LayerAgent output (mckinsey_v4) replaces layeragent_v3 in the table.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REF = ROOT / "data" / "eval_dataset" / "slides" / "process_flow_mckinsey_blue_transformation.png"
HTML_DIR = ROOT / "results" / "mckinsey_eval" / "html"
PNG_DIR = ROOT / "results" / "mckinsey_eval" / "png"

# Replace v3 in the eval dir with the latest v4 build.
LATEST_V4_HTML = ROOT / "results" / "debug" / "mckinsey_v4" / "99_final.html"

CANDIDATES = ["layeragent_v4", "layeragent_v1", "single_pass", "visual_cot", "cot_h_rag"]


def render(html: Path, png: Path) -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page = ctx.new_page()
        try:
            page.goto(f"file://{html.resolve()}", wait_until="networkidle", timeout=15000)
        except Exception:
            page.goto(f"file://{html.resolve()}", wait_until="load", timeout=15000)
        page.wait_for_timeout(200)
        page.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": 1280, "height": 720})
        b.close()


def main():
    from experiments.metrics.design_fidelity import all_design_metrics

    # Stage v4 from the latest debug run as the "layeragent_v4" row.
    if LATEST_V4_HTML.exists():
        v4_html = HTML_DIR / "layeragent_v4.html"
        v4_html.write_text(LATEST_V4_HTML.read_text())
        render(v4_html, PNG_DIR / "layeragent_v4.png")
        print(f"[stage] layeragent_v4 ← {LATEST_V4_HTML}")

    # Re-render others (deterministic) for fair comparison.
    for name in ("layeragent_v1", "single_pass", "visual_cot", "cot_h_rag"):
        h = HTML_DIR / f"{name}.html"
        if h.exists():
            render(h, PNG_DIR / f"{name}.png")
            print(f"[render] {name}")

    rows = []
    for name in CANDIDATES:
        h = HTML_DIR / f"{name}.html"
        png = PNG_DIR / f"{name}.png"
        if not (h.exists() and png.exists()):
            print(f"[skip] {name}")
            continue
        print(f"[metric] {name} ...")
        m = all_design_metrics(REF, h, png, skip_judge=False)
        m["method"] = name
        rows.append(m)

    # Pretty table
    print("\n=== McKinsey Design Fidelity (SOTA-aligned) ===")
    hdr = (
        f"{'method':<16} "
        f"{'BM-F1':>6} {'Eluo':>5} {'ΔE↓':>5} | "
        f"{'WS↓':>5} {'COL↓':>5} | "
        f"{'Lo':>3} {'Co':>3}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(
            f"{r['method']:<16} "
            f"{r.get('block_match_f1', 0):>6.3f} "
            f"{r.get('element_iou', 0):>5.3f} "
            f"{r.get('color_ciede2000', float('nan')):>5.1f} | "
            f"{r.get('whitespace_frac', 0):>5.2f} "
            f"{r.get('collision_score', 0):>5.2f} | "
            f"{r.get('layout_0_5', 0):>3} "
            f"{r.get('color_0_5', 0):>3}"
        )

    print("\nLegend: BM-F1 ↑ Block-Match F1 (Design2Code) | Eluo ↑ Element-IoU mean (Hungarian) | "
          "ΔE ↓ CIEDE2000 color distance (lower better)")
    print("        WS ↓ Excessive Whitespace fraction (AeSlides) | COL ↓ Collision score 0..1")
    print("        Lo / Co — AutoPresent 0-5 GPT-4o judge for Layout / Color")

    # Composite ranking — equal-weight z-scores (lower-is-better metrics inverted).
    import math
    keys_higher = ["block_match_f1", "element_iou", "layout_0_5", "color_0_5"]
    keys_lower = ["color_ciede2000", "whitespace_frac", "collision_score"]

    def safe(v):
        return v if isinstance(v, (int, float)) and not math.isnan(v) else None

    by_key_vals = {k: [safe(r.get(k)) for r in rows] for k in keys_higher + keys_lower}

    def zscore(vals, v, invert=False):
        clean = [x for x in vals if x is not None]
        if not clean or v is None:
            return 0.0
        mu = sum(clean) / len(clean)
        sd = (sum((x - mu) ** 2 for x in clean) / len(clean)) ** 0.5 or 1.0
        z = (v - mu) / sd
        return -z if invert else z

    print("\n=== Composite ranking (mean z-score, higher = closer to reference) ===")
    composite = []
    for r in rows:
        zs = []
        for k in keys_higher:
            zs.append(zscore(by_key_vals[k], safe(r.get(k)), invert=False))
        for k in keys_lower:
            zs.append(zscore(by_key_vals[k], safe(r.get(k)), invert=True))
        composite.append((r["method"], sum(zs) / len(zs)))
    composite.sort(key=lambda x: -x[1])
    for name, z in composite:
        print(f"  {name:<18} z = {z:+.2f}")

    out = ROOT / "results" / "mckinsey_eval" / "design_fidelity.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"\nsaved → {out}")


if __name__ == "__main__":
    main()
