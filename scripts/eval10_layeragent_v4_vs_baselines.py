"""10-slide eval: layeragent_v4 (chat-mode, current upgraded code) vs
existing single_pass / cot_h_rag / visual_cot outputs, scored by the new
SOTA-aligned design-fidelity metric pack.

For each of 10 selected slides:
  1. Use chat_parser to extract content from the reference image
  2. Run upgraded LayerAgent in chat mode → results/raw/layeragent_v4/<sid>_seed0.html
  3. Render PNG → results/screenshots/layeragent_v4/<sid>.png
  4. Compute design_fidelity metrics for all 4 methods × 10 slides
  5. Per-slide table + aggregate composite ranking
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REF_DIR = ROOT / "data" / "eval_dataset" / "slides"
RAW = ROOT / "results" / "raw"
SHOTS = ROOT / "results" / "screenshots"
OUT_DIR = ROOT / "results" / "eval10_v4"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 10 slides covering 9 layout categories (1 from each + 1 extra for design)
SLIDES = [
    "process_flow_mckinsey_blue_transformation",
    "matrix_2x2_mckinsey_blue_risk",
    "pyramid_mckinsey_blue_executive_summary",
    "waterfall_mckinsey_blue_finance",
    "mekko_mckinsey_blue_finance",
    "bar_chart_mckinsey_blue_performance",
    "line_chart_mckinsey_blue_trend",
    "harvey_table_mckinsey_blue_options",
    "design_02_dashboard",
    "design_08_roadmap",
]

METHODS = ["layeragent_v4", "single_pass", "cot_h_rag", "visual_cot"]

GENERIC_USER_MSG = (
    "이 슬라이드 디자인을 가능한 한 정확히 재현해줘. "
    "이미지에 보이는 모든 콘텐츠 (제목, 부제, 항목별 텍스트, 라벨, 수치)를 빠짐없이 보존하고, "
    "원본의 색상 팔레트와 레이아웃 형태도 그대로 유지해."
)


def gen_layeragent_v4(slide_id: str) -> Path:
    """Run upgraded LayerAgent in chat mode using the eval_dataset reference image."""
    from layeragent import LayerAgent
    from layeragent.utils.common import save_run

    img = REF_DIR / f"{slide_id}.png"
    if not img.exists():
        raise FileNotFoundError(img)
    agent = LayerAgent(model="gpt-4o")
    html, _spec = agent.run_from_chat(
        image_path=str(img),
        user_message=GENERIC_USER_MSG,
        slide_id=slide_id,
    )
    return save_run("layeragent_v4", slide_id, 0, html)


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
    # Stage 1 — generate layeragent_v4 outputs for the 10 slides
    print(f"[stage1] generating layeragent_v4 for {len(SLIDES)} slides")
    out_html_dir = RAW / "layeragent_v4"
    out_html_dir.mkdir(parents=True, exist_ok=True)
    for sid in SLIDES:
        out = out_html_dir / f"{sid}_seed0.html"
        if out.exists():
            print(f"  ~ skip (exists) {sid}")
            continue
        t0 = time.time()
        try:
            p = gen_layeragent_v4(sid)
            print(f"  ✓ {sid}  ({time.time()-t0:.1f}s)  → {p.name}")
        except Exception as e:
            print(f"  ✗ {sid}  {type(e).__name__}: {e}")

    # Stage 2 — render PNGs (all 4 methods × 10 slides)
    print(f"\n[stage2] rendering PNGs")
    for method in METHODS:
        png_dir = SHOTS / method
        png_dir.mkdir(parents=True, exist_ok=True)
        for sid in SLIDES:
            html = RAW / method / f"{sid}_seed0.html"
            png = png_dir / f"{sid}.png"
            if not html.exists():
                print(f"  ~ miss html  {method}/{sid}")
                continue
            if png.exists() and png.stat().st_mtime > html.stat().st_mtime:
                continue
            try:
                render(html, png)
                print(f"  → {method}/{sid}.png")
            except Exception as e:
                print(f"  ✗ {method}/{sid} render: {e}")

    # Stage 3 — design fidelity metrics
    from experiments.metrics.design_fidelity import all_design_metrics

    print(f"\n[stage3] computing metrics ({len(METHODS) * len(SLIDES)} cells)")
    all_rows: list[dict] = []
    for method in METHODS:
        for sid in SLIDES:
            ref = REF_DIR / f"{sid}.png"
            html = RAW / method / f"{sid}_seed0.html"
            png = SHOTS / method / f"{sid}.png"
            if not (ref.exists() and html.exists() and png.exists()):
                continue
            t0 = time.time()
            try:
                m = all_design_metrics(ref, html, png, skip_judge=False)
                m["method"] = method
                m["slide"] = sid
                m["_elapsed_s"] = round(time.time() - t0, 1)
                all_rows.append(m)
                print(f"  {method:<14} / {sid:<45}  "
                      f"BM={m.get('block_match_f1', 0):.2f} "
                      f"Eluo={m.get('element_iou', 0):.2f} "
                      f"WS={m.get('whitespace_frac', 0):.2f} "
                      f"({m['_elapsed_s']}s)")
            except Exception as e:
                print(f"  ✗ {method}/{sid}: {type(e).__name__}: {e}")

    # Stage 4 — aggregate
    out_jsonl = OUT_DIR / "rows.jsonl"
    with out_jsonl.open("w") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nsaved → {out_jsonl}")

    # Mean per method
    import math
    from statistics import mean

    keys_higher = ["block_match_f1", "element_iou", "layout_0_5", "color_0_5"]
    keys_lower = ["color_ciede2000", "whitespace_frac", "collision_score"]

    def safe(v):
        return v if isinstance(v, (int, float)) and not math.isnan(v) else None

    agg = {}
    for method in METHODS:
        rows = [r for r in all_rows if r["method"] == method]
        agg[method] = {}
        for k in keys_higher + keys_lower:
            vals = [safe(r.get(k)) for r in rows]
            vals = [v for v in vals if v is not None]
            agg[method][k] = mean(vals) if vals else float("nan")

    print("\n=== Aggregate (mean across 10 slides) ===")
    hdr = (f"{'method':<16} "
           f"{'BM-F1↑':>7} {'EIoU↑':>6} {'ΔE↓':>6} | "
           f"{'WS↓':>5} {'COL↓':>5} | {'Lo':>3} {'Co':>3}")
    print(hdr)
    print("-" * len(hdr))
    for method in METHODS:
        a = agg[method]
        print(f"{method:<16} "
              f"{a['block_match_f1']:>7.3f} {a['element_iou']:>6.3f} {a['color_ciede2000']:>6.1f} | "
              f"{a['whitespace_frac']:>5.2f} {a['collision_score']:>5.2f} | "
              f"{a['layout_0_5']:>3.1f} {a['color_0_5']:>3.1f}")

    # Composite z-ranking using per-slide z then averaging
    print("\n=== Composite ranking (per-slide z, averaged) ===")

    def zscores(values, invert=False):
        clean = [v for v in values if v is not None]
        if not clean:
            return [0.0] * len(values)
        mu = sum(clean) / len(clean)
        sd = (sum((x - mu) ** 2 for x in clean) / len(clean)) ** 0.5 or 1.0
        out = []
        for v in values:
            if v is None:
                out.append(0.0)
            else:
                z = (v - mu) / sd
                out.append(-z if invert else z)
        return out

    method_zs: dict[str, list[float]] = {m: [] for m in METHODS}
    for sid in SLIDES:
        for k in keys_higher:
            vals = [safe(next((r.get(k) for r in all_rows if r["method"] == m and r["slide"] == sid), None))
                    for m in METHODS]
            zs = zscores(vals, invert=False)
            for m, z in zip(METHODS, zs):
                method_zs[m].append(z)
        for k in keys_lower:
            vals = [safe(next((r.get(k) for r in all_rows if r["method"] == m and r["slide"] == sid), None))
                    for m in METHODS]
            zs = zscores(vals, invert=True)
            for m, z in zip(METHODS, zs):
                method_zs[m].append(z)
    composite = sorted(((m, mean(zs) if zs else 0.0) for m, zs in method_zs.items()),
                       key=lambda x: -x[1])
    for m, z in composite:
        print(f"  {m:<16} z = {z:+.3f}")

    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps({
        "n_slides": len(SLIDES),
        "agg_means": agg,
        "composite_z": dict(composite),
    }, ensure_ascii=False, indent=2))
    print(f"\nsummary → {summary_path}")


if __name__ == "__main__":
    main()
