#!/usr/bin/env python3
"""
실험: A(Baseline) vs E(Layer Agents v2) vs F(LangGraph Coordinate Passing) 비교.
저장된 Gemini 디자인 이미지 사용. 원본(AIDX PPT)도 함께 비교.
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
from src.methods.baseline import generate as baseline_generate
from src.methods.layer_agents_v2 import generate_from_saved_image as layer_v2_generate
from src.methods.layer_agents_langgraph import generate_from_saved_image as langgraph_generate

client = OpenAI()
DATA_DIR = Path(__file__).parent / "data" / "design_images"
RESULTS_DIR = Path(__file__).parent / "results" / "experiment_lg"
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


def wrap_slides(slides, title):
    parts = "\n".join(
        f'<div style="width:1280px;height:720px;margin:30px auto;box-shadow:0 20px 60px rgba(0,0,0,0.3);overflow:hidden;position:relative;">{s}</div>'
        for s in slides
    )
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><title>{title}</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;padding:40px;display:flex;flex-direction:column;align-items:center;gap:30px;}}</style>
</head><body>{parts}</body></html>"""


def main():
    with open(DATA_DIR / "session_meta.json") as f:
        meta = json.load(f)

    slide_contents = meta.get("slide_contents", [])
    style = meta.get("research_brief", {}).get("style", {})

    # 원본 HTML 복사
    original_html = (DATA_DIR / "original.html").read_text()
    (RESULTS_DIR / "original.html").write_text(original_html)

    print("=" * 70)
    print("Experiment: A(Baseline) vs E(Layer v2) vs F(LangGraph Coord-Pass)")
    print(f"Slides: {len(slide_contents)}, saved Gemini images")
    print("=" * 70)

    a_slides, e_slides, f_slides = [], [], []
    metrics = []

    for sc in slide_contents[:4]:
        sid = sc.get("slide_id", "")
        stype = sc.get("type", "")
        content = sc.get("content", {})
        img_path = DATA_DIR / f"{sid}_design.png"

        if not img_path.exists():
            print(f"\n  {sid}: 이미지 없음, 스킵")
            continue

        b64 = base64.b64encode(img_path.read_bytes()).decode()

        print(f"\n{'─'*60}")
        print(f"  {sid} ({stype})")
        print(f"{'─'*60}")

        slide_metrics = {"slide_id": sid, "type": stype}

        # ── Method A: Baseline ──
        print(f"  [A] Baseline...", end=" ", flush=True)
        t0 = time.time()
        raw_a = baseline_generate(client, b64)
        html_a = extract_html(raw_a)
        a_slides.append(html_a)
        dt_a = time.time() - t0
        slide_metrics["A"] = {"chars": len(html_a), "time": round(dt_a, 1)}
        print(f"{len(html_a)} chars ({dt_a:.0f}s)")

        # ── Method E: Layer Agents v2 ──
        print(f"  [E] Layer Agents v2...", end=" ", flush=True)
        t0 = time.time()
        result_e = layer_v2_generate(client, str(img_path), sid, stype, content, style)
        e_slides.append(result_e["assembled"])
        dt_e = time.time() - t0
        layers_e = result_e["layers"]
        slide_metrics["E"] = {
            "chars": len(result_e["assembled"]),
            "time": round(dt_e, 1),
            "layer_chars": {k: len(v) for k, v in layers_e.items()},
        }
        print(f"{len(result_e['assembled'])} chars ({dt_e:.0f}s)")
        print(f"      bg={len(layers_e['bg'])} cards={len(layers_e['cards'])} "
              f"content={len(layers_e['content'])} icons={len(layers_e['icons'])}")

        # ── Method F: LangGraph Coordinate Passing ──
        print(f"  [F] LangGraph Coord-Pass...", end=" ", flush=True)
        t0 = time.time()
        result_f = langgraph_generate(str(img_path), sid, stype, content, style)
        f_slides.append(result_f["assembled"])
        dt_f = time.time() - t0
        layers_f = result_f["layers"]
        bboxes = result_f.get("card_bboxes", [])
        slide_metrics["F"] = {
            "chars": len(result_f["assembled"]),
            "time": round(dt_f, 1),
            "layer_chars": {k: len(v) for k, v in layers_f.items()},
            "card_bboxes_count": len(bboxes),
        }
        print(f"{len(result_f['assembled'])} chars ({dt_f:.0f}s)")
        print(f"      bg={len(layers_f['bg'])} cards={len(layers_f['cards'])} "
              f"content={len(layers_f['content'])} icons={len(layers_f['icons'])}")
        print(f"      card_bboxes: {len(bboxes)} cards detected")
        if bboxes:
            for bbox in bboxes[:3]:
                ca = bbox.get("content_area", {})
                print(f"        {bbox.get('card_id', '?')}: "
                      f"({bbox.get('left',0)}%, {bbox.get('top',0)}%) "
                      f"{bbox.get('width',0)}%x{bbox.get('height',0)}% "
                      f"→ content: ({ca.get('left',0)}%, {ca.get('top',0)}%)")

        metrics.append(slide_metrics)

    # HTML 파일 생성
    (RESULTS_DIR / "method_a.html").write_text(wrap_slides(a_slides, "Method A: Baseline"))
    (RESULTS_DIR / "method_e.html").write_text(wrap_slides(e_slides, "Method E: Layer Agents v2"))
    (RESULTS_DIR / "method_f.html").write_text(wrap_slides(f_slides, "Method F: LangGraph Coord-Pass"))

    # Metrics JSON
    (RESULTS_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2))

    print(f"\n{'=' * 70}")
    print("완료! 비교:")
    print(f"  원본:     {RESULTS_DIR / 'original.html'}")
    print(f"  Method A: {RESULTS_DIR / 'method_a.html'}")
    print(f"  Method E: {RESULTS_DIR / 'method_e.html'}")
    print(f"  Method F: {RESULTS_DIR / 'method_f.html'}")
    print(f"  Metrics:  {RESULTS_DIR / 'metrics.json'}")


if __name__ == "__main__":
    main()
