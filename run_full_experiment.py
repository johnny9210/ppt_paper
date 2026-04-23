#!/usr/bin/env python3
"""
본 실험: 10개 디자인 × 5개 method (A/B/C/E/F) + 4개 메트릭 평가.
결과를 results/full_experiment/에 저장.
"""

import base64
import json
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI

client = OpenAI()
DATA_DIR = Path(__file__).parent / "data" / "experiment_designs"
RESULTS_DIR = Path(__file__).parent / "results" / "full_experiment"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def extract_html(text):
    text = text.strip()
    if "```html" in text:
        text = text.split("```html", 1)[1].split("```")[0]
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
    start = re.search(r"<(?:style|div|!DOCTYPE)", text, re.IGNORECASE)
    if start and start.start() > 0:
        text = text[start.start():]
    return text.strip()


def wrap_slide(html_content):
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;display:flex;justify-content:center;align-items:center;min-height:100vh;}}</style>
</head><body>
<div style="width:1280px;height:720px;overflow:hidden;position:relative;">{html_content}</div>
</body></html>"""


def main():
    with open(DATA_DIR / "meta.json") as f:
        meta = json.load(f)

    style = meta["style"]
    slides = meta["slides"]

    print("=" * 70)
    print(f"Full Experiment: {len(slides)} designs × 5 methods")
    print("=" * 70)

    all_results = {}

    for si, slide in enumerate(slides):
        sid = slide["id"]
        stype = slide["type"]
        content = slide["content"]
        img_path = DATA_DIR / f"{sid}.png"

        if not img_path.exists():
            print(f"\n  {sid}: image not found, skip")
            continue

        b64 = base64.b64encode(img_path.read_bytes()).decode()
        slide_dir = RESULTS_DIR / sid
        slide_dir.mkdir(exist_ok=True)

        print(f"\n{'━'*70}")
        print(f"  [{si+1}/{len(slides)}] {sid} ({stype})")
        print(f"{'━'*70}")

        slide_results = {}

        # ── Check if already done ──
        results_file = slide_dir / "results.json"
        if results_file.exists():
            print(f"  Already done, loading cached results")
            with open(results_file) as f:
                all_results[sid] = json.load(f)
            continue

        # ── A: Baseline ──
        print(f"  [A] Baseline...", end=" ", flush=True)
        from src.methods.baseline import generate_with_content as a_gen
        t0 = time.time()
        html_a = extract_html(a_gen(client, b64, content))
        slide_results["A"] = {"html": html_a, "time": round(time.time()-t0, 1)}
        print(f"{len(html_a)} chars ({slide_results['A']['time']:.0f}s)")

        # ── B: Visual CoT ──
        print(f"  [B] Visual CoT...", end=" ", flush=True)
        from src.methods.visual_cot import generate_with_content as b_gen
        t0 = time.time()
        _, html_b = b_gen(client, b64, content)
        html_b = extract_html(html_b)
        slide_results["B"] = {"html": html_b, "time": round(time.time()-t0, 1)}
        print(f"{len(html_b)} chars ({slide_results['B']['time']:.0f}s)")

        # ── C: CoT + H-RAG ──
        print(f"  [C] CoT+H-RAG...", end=" ", flush=True)
        from src.methods.cot_hrag import generate_with_content as c_gen
        t0 = time.time()
        _, _, html_c = c_gen(client, b64, content)
        html_c = extract_html(html_c)
        slide_results["C"] = {"html": html_c, "time": round(time.time()-t0, 1)}
        print(f"{len(html_c)} chars ({slide_results['C']['time']:.0f}s)")

        # ── E: Layer Agents v2 ──
        print(f"  [E] Layer Agents...", end=" ", flush=True)
        from src.methods.layer_agents_v2 import generate_from_saved_image as e_gen
        t0 = time.time()
        result_e = e_gen(client, str(img_path), sid, stype, content, style)
        slide_results["E"] = {"html": result_e["assembled"], "time": round(time.time()-t0, 1)}
        print(f"{len(result_e['assembled'])} chars ({slide_results['E']['time']:.0f}s)")

        # ── F: LayerAgent ──
        print(f"  [F] LayerAgent...", end=" ", flush=True)
        import src.methods.layer_agents_langgraph as lg
        lg._pipeline = None
        from src.methods.layer_agents_langgraph import generate_from_saved_image as f_gen
        t0 = time.time()
        result_f = f_gen(str(img_path), sid, stype, content, style)
        slide_results["F"] = {
            "html": result_f["assembled"],
            "time": round(time.time()-t0, 1),
            "bboxes": len(result_f.get("card_bboxes", [])),
        }
        print(f"{len(result_f['assembled'])} chars ({slide_results['F']['time']:.0f}s) bbox={slide_results['F']['bboxes']}")

        # ── Save HTML + Screenshots ──
        for method, data in slide_results.items():
            (slide_dir / f"{method}.html").write_text(wrap_slide(data["html"]))

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            for method in slide_results:
                page.goto(f"file://{slide_dir / f'{method}.html'}")
                page.wait_for_timeout(1000)
                page.screenshot(path=str(slide_dir / f"{method}.png"))
            browser.close()

        # ── Evaluate ──
        from src.metrics.content_completeness import content_completeness_rate
        from src.metrics.layer_ordering import layer_ordering_accuracy
        from src.metrics.css_effect_preservation import css_richness
        from src.metrics.icon_integrity import icon_integrity_rate

        eval_data = {}
        for method, data in slide_results.items():
            html = data["html"]
            ccr = content_completeness_rate(content, html)
            loa = layer_ordering_accuracy(html)
            cr = css_richness(html)
            iir = icon_integrity_rate(html)
            eval_data[method] = {
                "CCR": ccr["rate"],
                "LOA": loa["z_index_usage_rate"],
                "LOA_levels": loa["unique_z_levels"],
                "CSS": cr["total_effects"],
                "Colors": cr["unique_colors"],
                "IIR": iir["rate"],
                "time": data["time"],
                "chars": len(data["html"]),
            }

        all_results[sid] = eval_data

        # Save per-slide results
        (slide_dir / "results.json").write_text(json.dumps(eval_data, indent=2))

        # Print slide summary
        print(f"  {'Method':<6} {'CCR':>5} {'LOA':>5} {'CSS':>5} {'Colors':>7} {'IIR':>5}")
        for m in ["A", "B", "C", "E", "F"]:
            r = eval_data[m]
            print(f"  {m:<6} {r['CCR']:>5.2f} {r['LOA']:>5.2f} {r['CSS']:>5} {r['Colors']:>7} {r['IIR']:>5.2f}")

    # ══════════════════════════════════════
    # 전체 요약
    # ══════════════════════════════════════
    print(f"\n{'═'*70}")
    print("전체 요약 (평균)")
    print(f"{'═'*70}")

    methods = ["A", "B", "C", "E", "F"]
    avg = {m: {"CCR": 0, "LOA": 0, "CSS": 0, "Colors": 0, "IIR": 0, "time": 0} for m in methods}
    n = len(all_results)

    for sid, evals in all_results.items():
        for m in methods:
            if m in evals:
                for k in avg[m]:
                    avg[m][k] += evals[m][k]

    print(f"{'Method':<6} {'CCR':>6} {'LOA':>6} {'CSS':>6} {'Colors':>7} {'IIR':>5} {'Time':>6}")
    print("-" * 50)
    for m in methods:
        print(f"{m:<6} {avg[m]['CCR']/n:>6.2f} {avg[m]['LOA']/n:>6.2f} {avg[m]['CSS']/n:>6.1f} {avg[m]['Colors']/n:>7.1f} {avg[m]['IIR']/n:>5.2f} {avg[m]['time']/n:>5.0f}s")

    # Save full results
    (RESULTS_DIR / "all_results.json").write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False)
    )
    (RESULTS_DIR / "averages.json").write_text(
        json.dumps({m: {k: round(v/n, 3) for k, v in avg[m].items()} for m in methods}, indent=2)
    )
    print(f"\nSaved: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
