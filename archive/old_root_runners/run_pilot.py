#!/usr/bin/env python3
"""
파일럿 실험: slide_003 (three_column) 하나로 A/B/C/E/F 5가지 방법 비교.
F+는 F의 edited 결과를 사용.
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
DATA_DIR = Path(__file__).parent / "data" / "design_images"
RESULTS_DIR = Path(__file__).parent / "results" / "pilot"
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


def wrap_slide(html_content, title):
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><title>{title}</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;display:flex;justify-content:center;align-items:center;min-height:100vh;}}</style>
</head><body>
<div style="width:1280px;height:720px;box-shadow:0 20px 60px rgba(0,0,0,0.3);overflow:hidden;position:relative;">{html_content}</div>
</body></html>"""


def main():
    # 메타데이터
    with open(DATA_DIR / "session_meta.json") as f:
        meta = json.load(f)

    style = meta["research_brief"]["style"]
    sc = meta["slide_contents"][2]  # slide_003 (three_column)
    sid = sc["slide_id"]
    stype = sc["type"]
    content = sc.get("content", {})
    img_path = DATA_DIR / f"{sid}_design.png"
    b64 = base64.b64encode(img_path.read_bytes()).decode()

    print("=" * 70)
    print(f"Pilot Experiment: {sid} ({stype})")
    print("=" * 70)

    results = {}

    # ── Method A: Baseline ──
    print(f"\n[A] Baseline...", end=" ", flush=True)
    from src.methods.baseline import generate as baseline_gen
    t0 = time.time()
    raw_a = baseline_gen(client, b64)
    html_a = extract_html(raw_a)
    dt = time.time() - t0
    results["A"] = {"html": html_a, "chars": len(html_a), "time": round(dt, 1)}
    print(f"{len(html_a)} chars ({dt:.0f}s)")

    # ── Method B: Visual CoT ──
    print(f"[B] Visual CoT...", end=" ", flush=True)
    from src.methods.visual_cot import generate as cot_gen
    t0 = time.time()
    analysis_b, raw_b = cot_gen(client, b64)
    html_b = extract_html(raw_b)
    dt = time.time() - t0
    results["B"] = {"html": html_b, "chars": len(html_b), "time": round(dt, 1)}
    print(f"{len(html_b)} chars ({dt:.0f}s)")

    # ── Method C: CoT + H-RAG ──
    print(f"[C] CoT + H-RAG...", end=" ", flush=True)
    from src.methods.cot_hrag import generate as hrag_gen
    t0 = time.time()
    analysis_c, patterns_c, raw_c = hrag_gen(client, b64)
    html_c = extract_html(raw_c)
    dt = time.time() - t0
    results["C"] = {"html": html_c, "chars": len(html_c), "time": round(dt, 1)}
    print(f"{len(html_c)} chars ({dt:.0f}s)")

    # ── Method E: Layer Agents (no coord sharing) ──
    print(f"[E] Layer Agents v2...", end=" ", flush=True)
    from src.methods.layer_agents_v2 import generate_from_saved_image as layer_v2_gen
    t0 = time.time()
    result_e = layer_v2_gen(client, str(img_path), sid, stype, content, style)
    html_e = result_e["assembled"]
    dt = time.time() - t0
    results["E"] = {"html": html_e, "chars": len(html_e), "time": round(dt, 1)}
    print(f"{len(html_e)} chars ({dt:.0f}s)")

    # ── Method F: LayerAgent (LangGraph, ours) ──
    print(f"[F] LayerAgent (ours)...", end=" ", flush=True)
    import src.methods.layer_agents_langgraph as lg
    lg._pipeline = None
    from src.methods.layer_agents_langgraph import generate_from_saved_image as lg_gen
    t0 = time.time()
    result_f = lg_gen(str(img_path), sid, stype, content, style)
    html_f = result_f["assembled"]
    html_f_edit = result_f["edited"]
    dt = time.time() - t0
    bboxes = result_f.get("card_bboxes", [])
    results["F"] = {"html": html_f, "chars": len(html_f), "time": round(dt, 1), "bboxes": len(bboxes)}
    results["F+"] = {"html": html_f_edit, "chars": len(html_f_edit), "time": 0}  # Edit time included in F
    print(f"{len(html_f)} chars → edit: {len(html_f_edit)} chars ({dt:.0f}s) bboxes={len(bboxes)}")

    # ── HTML 파일 저장 ──
    for method, data in results.items():
        fname = f"method_{method.replace('+', 'plus')}.html"
        (RESULTS_DIR / fname).write_text(wrap_slide(data["html"], f"Method {method}"))

    # ── 원본 디자인 이미지도 표시용으로 저장 ──
    # (이미지를 <img>로 보여주는 HTML)
    orig_html = f'<img src="data:image/png;base64,{b64}" style="width:1280px;height:720px;object-fit:contain;">'
    (RESULTS_DIR / "original_design.html").write_text(wrap_slide(orig_html, "Original Design"))

    # ── 스크린샷 촬영 ──
    print(f"\n스크린샷 촬영...", flush=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        for method in ["A", "B", "C", "E", "F", "Fplus"]:
            fname = f"method_{method}.html"
            page.goto(f"file://{RESULTS_DIR / fname}")
            page.wait_for_timeout(1500)
            page.screenshot(path=str(RESULTS_DIR / f"method_{method}.png"))
            print(f"  {method}.png", flush=True)
        browser.close()

    # ── 결과 요약 ──
    print(f"\n{'=' * 70}")
    print("결과 요약:")
    print(f"{'Method':<8} {'Chars':>8} {'Time':>6} {'Notes'}")
    print("-" * 50)
    for method, data in results.items():
        notes = f"bboxes={data.get('bboxes', '-')}" if 'bboxes' in data else ""
        print(f"{method:<8} {data['chars']:>8} {data['time']:>5.0f}s {notes}")

    # metrics JSON
    metrics = {method: {k: v for k, v in data.items() if k != "html"} for method, data in results.items()}
    (RESULTS_DIR / "pilot_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"\nSaved to: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
