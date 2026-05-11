"""Main evaluation pipeline — runs 5 methods × N slides × 6 metrics.

Four cacheable stages (each restartable):

  Stage 1: Generate HTML  — for each (method, slide) → results/raw/{method}/{sid}_seed0.html
  Stage 2: Render PNG     — for each HTML → results/screenshots/{method}/{sid}.png
  Stage 3: Reference perception — VLM lists layers in each ref image (cached)
  Stage 4: Compute metrics — CLIP/BlockMatch/Position/RenderRate/LTED  (SSIM removed)

Output:
  results/main_eval/eval_results.jsonl
  results/main_eval/eval_summary.csv

Usage:
  python -m experiments.main_eval                       # full pipeline
  python -m experiments.main_eval --stage 1             # only stage 1
  python -m experiments.main_eval --methods single_pass # restrict
  python -m experiments.main_eval --limit 5             # only first 5 slides
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from openai import OpenAI

from experiments.metrics.lted import lted_from_perception_text
from experiments.metrics.ocr_blocks import extract_blocks
from experiments.metrics.position import position_alignment
from experiments.metrics.render_rate import render_one
from experiments.metrics.structural import block_match
from experiments.probing.layer_tree import PERCEPTION_PROMPT
from layeragent.utils.common import b64_image, get_image_path, load_active_specs


METHODS = ["single_pass", "visual_cot", "cot_h_rag", "layeragent"]
RESULTS_DIR = _ROOT / "results"
RAW_DIR = RESULTS_DIR / "raw"
SHOTS_DIR = RESULTS_DIR / "screenshots"
EVAL_DIR = RESULTS_DIR / "main_eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)
PERCEPTION_DIR = _ROOT / "data" / "eval_dataset" / "perception"
PERCEPTION_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────
# Stage 1 — Generate HTML for each (method, slide)
# ─────────────────────────────────────────────────────────────────
def stage1_generate(designs: list[str], methods: list[str]) -> None:
    from baselines import single_pass, visual_cot, cot_h_rag
    from layeragent import LayerAgent
    from layeragent.utils.common import save_run

    BASELINES = {"single_pass": single_pass, "visual_cot": visual_cot, "cot_h_rag": cot_h_rag}

    for method in methods:
        for did in designs:
            out = RAW_DIR / method / f"{did}_seed0.html"
            if out.exists():
                continue
            print(f"  [gen] {method} / {did} ...", flush=True)
            try:
                if method == "layeragent":
                    agent = LayerAgent(model="gpt-4o")
                    html = agent.run(did)
                else:
                    html = BASELINES[method].run(did)
                save_run(method, did, 0, html)
                print(f"    ✓ {len(html)} chars")
            except Exception as e:
                print(f"    ✗ {type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────────
# Stage 2 — Render HTML to PNG
# ─────────────────────────────────────────────────────────────────
def stage2_render(designs: list[str], methods: list[str]) -> None:
    from playwright.sync_api import sync_playwright

    pairs: list[tuple[Path, Path]] = []
    for method in methods:
        out_dir = SHOTS_DIR / method
        out_dir.mkdir(parents=True, exist_ok=True)
        for did in designs:
            html = RAW_DIR / method / f"{did}_seed0.html"
            png = out_dir / f"{did}.png"
            if html.exists() and not png.exists():
                pairs.append((html, png))

    if not pairs:
        print("  [render] all up-to-date")
        return

    print(f"  [render] {len(pairs)} screenshots")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=2)
        page = ctx.new_page()
        for html_path, png_path in pairs:
            try:
                page.goto(f"file://{html_path.resolve()}", wait_until="networkidle", timeout=15000)
            except Exception:
                page.goto(f"file://{html_path.resolve()}", wait_until="load", timeout=15000)
            page.wait_for_timeout(300)
            page.screenshot(path=str(png_path),
                            clip={"x": 0, "y": 0, "width": 1280, "height": 720})
        browser.close()


# ─────────────────────────────────────────────────────────────────
# Stage 3 — Cache reference perception (VLM "describe the layers")
# ─────────────────────────────────────────────────────────────────
def stage3_perception(designs: list[str], model: str = "gpt-4o-2024-08-06") -> None:
    client = OpenAI()
    for did in designs:
        out = PERCEPTION_DIR / f"{did}.txt"
        if out.exists():
            continue
        print(f"  [perc] {did} ...", flush=True)
        try:
            img_b64 = b64_image(did)
            resp = client.chat.completions.create(
                model=model,
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                        {"type": "text", "text": PERCEPTION_PROMPT},
                    ],
                }],
            )
            text = resp.choices[0].message.content or ""
            out.write_text(text)
            print(f"    ✓ {len(text.splitlines())} lines")
        except Exception as e:
            print(f"    ✗ {type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────────
# Stage 4 — Compute metrics
# ─────────────────────────────────────────────────────────────────
def stage4_metrics(designs: list[str], methods: list[str],
                   skip_clip: bool = True) -> list[dict]:
    rows: list[dict] = []
    for did in designs:
        ref_img = get_image_path(did)
        perc_path = PERCEPTION_DIR / f"{did}.txt"
        perc_text = perc_path.read_text() if perc_path.exists() else ""

        # Reference OCR blocks (compute once per slide)
        try:
            ref_blocks = extract_blocks(ref_img)
        except Exception:
            ref_blocks = []

        for method in methods:
            html_path = RAW_DIR / method / f"{did}_seed0.html"
            png_path = SHOTS_DIR / method / f"{did}.png"
            row = {"design_id": did, "method": method}

            # Render rate (from HTML)
            if html_path.exists():
                try:
                    rr = render_one(html_path.read_text())
                    row["render_ok"] = bool(rr.get("rendered"))
                    row["render_visible_count"] = rr.get("n_visible", 0)
                except Exception as e:
                    row["render_ok"] = False
                    row["render_err"] = str(e)
            else:
                row["render_ok"] = False
                row["render_err"] = "no html"

            if png_path.exists() and ref_img.exists():
                # SSIM intentionally not computed — see paper decision (commit 768b0cb).
                # Position + Block-Match (OCR-based)
                try:
                    gen_blocks = extract_blocks(png_path)
                    row["block_match"] = block_match(ref_blocks, gen_blocks)
                    row["position"] = position_alignment(ref_blocks, gen_blocks,
                                                          image_width=1280,
                                                          image_height=720)
                    row["n_ref_blocks"] = len(ref_blocks)
                    row["n_gen_blocks"] = len(gen_blocks)
                except Exception as e:
                    row["bm_err"] = str(e)

                # CLIP (optional; heavy)
                if not skip_clip:
                    try:
                        from experiments.metrics.structural import clip_similarity
                        row["clip"] = clip_similarity(str(ref_img), str(png_path))
                    except Exception as e:
                        row["clip_err"] = str(e)

            # LTED (from perception text + generated HTML)
            if perc_text and html_path.exists():
                try:
                    lted_r = lted_from_perception_text(perc_text, html_path.read_text())
                    row["lted"] = lted_r["lted"]
                    row["layer_recall"] = lted_r["layer_recall"]
                    row["n_ref_layers"] = lted_r["n_ref_layers"]
                    row["n_gen_layers"] = lted_r["n_gen_layers"]
                except Exception as e:
                    row["lted_err"] = str(e)

            rows.append(row)
            print(f"  [metric] {method:>14} / {did}: "
                  f"BM={row.get('block_match', '—')!s:>5}  "
                  f"Pos={row.get('position', '—')!s:>5}  "
                  f"LTED={row.get('lted', '—')!s:>5}  "
                  f"render={row.get('render_ok', '—')!s:>5}")
    return rows


def write_outputs(rows: list[dict]) -> None:
    out_jsonl = EVAL_DIR / "eval_results.jsonl"
    with out_jsonl.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # CSV summary
    out_csv = EVAL_DIR / "eval_summary.csv"
    headers = ["design_id", "method", "block_match", "position",
               "lted", "layer_recall", "render_ok", "n_ref_layers", "n_gen_layers"]
    with out_csv.open("w") as f:
        f.write(",".join(headers) + "\n")
        for r in rows:
            f.write(",".join(str(r.get(h, "")) for h in headers) + "\n")
    print(f"\n  → {out_jsonl}")
    print(f"  → {out_csv}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=int, choices=[1, 2, 3, 4],
                   help="run only one stage")
    p.add_argument("--methods", nargs="+", default=METHODS)
    p.add_argument("--limit", type=int, default=None,
                   help="cap number of designs (for smoke testing)")
    p.add_argument("--no-clip", action="store_true", help="skip CLIP metric (heavy)")
    args = p.parse_args()

    specs = load_active_specs()
    designs = [s["id"] for s in specs]
    if args.limit:
        designs = designs[:args.limit]

    print(f"[main_eval] designs={len(designs)} methods={args.methods}")
    t0 = time.time()

    if args.stage in (None, 1):
        print("\n=== Stage 1: Generate HTML ===")
        stage1_generate(designs, args.methods)
    if args.stage in (None, 2):
        print("\n=== Stage 2: Render PNG ===")
        stage2_render(designs, args.methods)
    if args.stage in (None, 3):
        print("\n=== Stage 3: Reference Perception ===")
        stage3_perception(designs)
    if args.stage in (None, 4):
        print("\n=== Stage 4: Compute Metrics ===")
        rows = stage4_metrics(designs, args.methods, skip_clip=args.no_clip)
        write_outputs(rows)

    print(f"\n[main_eval] done in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
