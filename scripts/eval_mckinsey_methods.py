"""Compare 4 baselines vs LayerAgent v1 (before upgrade) vs LayerAgent v3
(after upgrade) on the single McKinsey reference image.

For each method:
  1. Generate HTML (already-generated for v1/v3; otherwise call now)
  2. Render PNG via Playwright
  3. Compute DOM metrics (VEC/EDC/VLC/CRP/HD/SC/ZDX)
  4. Compute visual metrics (CLIP/LPIPS — SSIM excluded by paper decision)
  5. Print side-by-side table

The McKinsey image has no entry in meta.json, so we bypass load_meta and pass
the chat_parser-extracted spec directly into each baseline's *prompt*.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layeragent.utils.common import extract_html, wrap_slide  # noqa: E402
from layeragent.utils.llm import vision_call, _openai_client  # noqa: E402

# Import baseline prompt templates directly (avoid their meta.json-bound run()).
from baselines.single_pass import PROMPT_WITH_CONTENT as SP_PROMPT  # noqa: E402
from baselines.visual_cot import (  # noqa: E402
    ANALYSIS_PROMPT as VCOT_ANALYSIS,
    GENERATE_PROMPT as VCOT_GENERATE,
)
from baselines.cot_h_rag import (  # noqa: E402
    ANALYSIS_PROMPT as CHR_ANALYSIS,
    GENERATE_PROMPT as CHR_GENERATE,
    _build_patterns_context,
)

IMAGE = ROOT / "data" / "eval_dataset" / "slides" / "process_flow_mckinsey_blue_transformation.png"
SPEC_PATH = ROOT / "results" / "debug" / "mckinsey_v3" / "00_chat_parser_spec.json"

OUT_DIR = ROOT / "results" / "mckinsey_eval"
HTML_DIR = OUT_DIR / "html"
PNG_DIR = OUT_DIR / "png"
HTML_DIR.mkdir(parents=True, exist_ok=True)
PNG_DIR.mkdir(parents=True, exist_ok=True)

# Pre-existing artifacts (from earlier runs)
LA_V1_HTML = ROOT / "results" / "raw" / "layeragent-debug-mckinsey" / "mckinsey_blue_transformation_seed0.html"
LA_V3_HTML = ROOT / "results" / "raw" / "layeragent-debug-mckinsey" / "mckinsey_blue_transformation_seed0.html"  # overwritten by v3 run? check below


def _img_b64() -> str:
    return base64.b64encode(IMAGE.read_bytes()).decode()


def _content_json() -> str:
    spec = json.loads(SPEC_PATH.read_text())
    return json.dumps(spec["content"], ensure_ascii=False, indent=2)


# ─────────────────── Generators ───────────────────

def gen_single_pass(image_b64: str, content_json: str, model: str) -> str:
    prompt = SP_PROMPT.format(content_json=content_json)
    raw = vision_call(image_b64, prompt, model, max_tokens=8000)
    return extract_html(raw)


def gen_visual_cot(image_b64: str, content_json: str, model: str) -> str:
    client = _openai_client()
    img_url = f"data:image/png;base64,{image_b64}"
    a = client.chat.completions.create(
        model=model, max_tokens=2000,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": img_url}},
            {"type": "text", "text": VCOT_ANALYSIS},
        ]}],
    ).choices[0].message.content
    g = client.chat.completions.create(
        model=model, max_tokens=8000,
        messages=[
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": img_url}},
                {"type": "text", "text": VCOT_ANALYSIS},
            ]},
            {"role": "assistant", "content": a},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": img_url}},
                {"type": "text", "text": VCOT_GENERATE.format(content_json=content_json)},
            ]},
        ],
    ).choices[0].message.content
    return extract_html(g)


def gen_cot_h_rag(image_b64: str, content_json: str, model: str) -> str:
    client = _openai_client()
    img_url = f"data:image/png;base64,{image_b64}"
    a = client.chat.completions.create(
        model=model, max_tokens=2000,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": img_url}},
            {"type": "text", "text": CHR_ANALYSIS},
        ]}],
    ).choices[0].message.content
    patterns = _build_patterns_context(a)
    g = client.chat.completions.create(
        model=model, max_tokens=8000,
        messages=[
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": img_url}},
                {"type": "text", "text": CHR_ANALYSIS},
            ]},
            {"role": "assistant", "content": a},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": img_url}},
                {"type": "text", "text": CHR_GENERATE.format(patterns=patterns, content_json=content_json)},
            ]},
        ],
    ).choices[0].message.content
    return extract_html(g)


# ─────────────────── Driver ───────────────────

METHODS_TO_GEN = {
    "single_pass": gen_single_pass,
    "visual_cot": gen_visual_cot,
    "cot_h_rag": gen_cot_h_rag,
}

# Pre-existing HTML artifacts (no regeneration)
PREEXISTING = {
    # v1 = layeragent BEFORE the 4-upgrade patch (already saved by first debug run)
    "layeragent_v1": ROOT / "results" / "debug" / "mckinsey_blue_transformation" / "99_final.html",
    # v3 = layeragent AFTER the 4-upgrade patch
    "layeragent_v3": ROOT / "results" / "debug" / "mckinsey_v3" / "99_final.html",
}


def write_html(method: str, html: str) -> Path:
    p = HTML_DIR / f"{method}.html"
    # If the html is a fragment, wrap. If it's already a full doc, write as-is.
    body = html.strip()
    if "<!DOCTYPE" not in body[:50] and "<html" not in body[:200]:
        body = wrap_slide(body)
    p.write_text(body)
    return p


def render_png(html_path: Path, png_path: Path) -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page = ctx.new_page()
        try:
            page.goto(f"file://{html_path.resolve()}", wait_until="networkidle", timeout=15000)
        except Exception:
            page.goto(f"file://{html_path.resolve()}", wait_until="load", timeout=15000)
        page.wait_for_timeout(200)
        page.screenshot(path=str(png_path), clip={"x": 0, "y": 0, "width": 1280, "height": 720})
        b.close()


def main():
    image_b64 = _img_b64()
    content_json = _content_json()
    print(f"[setup] image: {IMAGE.name} | content: {SPEC_PATH.parent.name}")

    htmls: dict[str, Path] = {}

    # 1) Pre-existing artifacts copied into eval dir
    for method, src in PREEXISTING.items():
        if not src.exists():
            print(f"[skip] {method}: {src} missing")
            continue
        dst = HTML_DIR / f"{method}.html"
        dst.write_text(src.read_text())
        htmls[method] = dst
        print(f"[copy] {method}: {src.name}")

    # 2) Generate baselines
    for method, gen_fn in METHODS_TO_GEN.items():
        print(f"[gen ] {method} ...")
        try:
            raw = gen_fn(image_b64, content_json, model="gpt-4o")
            htmls[method] = write_html(method, raw)
            print(f"       saved {htmls[method].name} ({len(raw)} chars)")
        except Exception as e:
            print(f"       FAILED: {type(e).__name__}: {e}")

    # 3) Render PNGs
    print("\n[render] PNGs")
    for method, h in htmls.items():
        png = PNG_DIR / f"{method}.png"
        try:
            render_png(h, png)
            print(f"  → {png.name}")
        except Exception as e:
            print(f"  ! {method} render failed: {e}")

    # 4) Metrics
    print("\n[metrics] DOM + visual ...")
    from experiments.metrics.dom_structure import extract_dom_metrics
    from experiments.metrics.visual_similarity import all_visual_metrics

    rows = []
    for method, h in htmls.items():
        png = PNG_DIR / f"{method}.png"
        try:
            dom = extract_dom_metrics(h)
        except Exception as e:
            print(f"  ! {method} DOM err: {e}")
            dom = {}
        try:
            vis = all_visual_metrics(IMAGE, png) if png.exists() else {}
        except Exception as e:
            print(f"  ! {method} VIS err: {e}")
            vis = {}
        row = {"method": method, **dom, **vis}
        rows.append(row)

    # 5) Print table
    print("\n=== McKinsey single-image evaluation ===")
    print(f"{'method':<20} {'VEC':>4} {'EDC':>4} {'VLC':>4} {'CRP':>4} {'HD':>3} {'SC':>5} | "
          f"{'CLIP':>6} {'LPIPS':>6}")
    print("-" * 80)
    for r in rows:
        print(f"{r['method']:<20} "
              f"{r.get('vec',0):>4} {r.get('edc',0):>4} {r.get('vlc',0):>4} {r.get('crp',0):>4} "
              f"{r.get('hd',0):>3} {r.get('sc',0):>5.2f} | "
              f"{r.get('clip',0):>6.3f} {r.get('lpips',0):>6.3f}")

    out_json = OUT_DIR / "metrics.json"
    out_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"\nsaved → {out_json}")


if __name__ == "__main__":
    main()
