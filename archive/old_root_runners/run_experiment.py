#!/usr/bin/env python3
"""
메인 실험: 저장된 Gemini 이미지로 A(Baseline) vs E(Layer Agents v2) 비교.
원본(AIDX PPT)도 함께 표시.
"""

import base64
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI
from src.methods.baseline import generate as baseline_generate
from src.methods.layer_agents_v2 import generate_from_saved_image as layer_generate

client = OpenAI()
DATA_DIR = Path(__file__).parent / "data" / "design_images"
RESULTS_DIR = Path(__file__).parent / "results" / "experiment"
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


def main():
    # 메타데이터 로드
    with open(DATA_DIR / "session_meta.json") as f:
        meta = json.load(f)

    slide_contents = meta.get("slide_contents", [])
    style = meta.get("research_brief", {}).get("style", {})

    # 원본 HTML 복사
    original_html = (DATA_DIR / "original.html").read_text()
    (RESULTS_DIR / "original.html").write_text(original_html)

    print("=" * 60)
    print("Experiment: Baseline (A) vs Layer Agents v2 (E)")
    print(f"Slides: {len(slide_contents)}, using saved Gemini images")
    print("=" * 60)

    a_slides = []
    e_slides = []

    for sc in slide_contents[:4]:
        sid = sc.get("slide_id", "")
        stype = sc.get("type", "")
        content = sc.get("content", {})
        img_path = DATA_DIR / f"{sid}_design.png"

        if not img_path.exists():
            print(f"\n  {sid}: 이미지 없음, 스킵")
            continue

        b64 = base64.b64encode(img_path.read_bytes()).decode()

        print(f"\n{'─'*50}")
        print(f"  {sid} ({stype})")
        print(f"{'─'*50}")

        # ── Method A: Baseline ──
        print(f"  [A] Baseline...", end=" ", flush=True)
        t0 = time.time()
        raw_a = baseline_generate(client, b64)
        html_a = extract_html(raw_a)
        a_slides.append(html_a)
        print(f"{len(html_a)} chars ({time.time()-t0:.0f}s)")

        # ── Method E: Layer Agents v2 ──
        print(f"  [E] Layer Agents v2...", end=" ", flush=True)
        t0 = time.time()
        result_e = layer_generate(client, str(img_path), sid, stype, content, style)
        e_slides.append(result_e["assembled"])
        layers = result_e["layers"]
        print(f"{len(result_e['assembled'])} chars ({time.time()-t0:.0f}s)")
        print(f"      bg={len(layers['bg'])} cards={len(layers['cards'])} content={len(layers['content'])} icons={len(layers['icons'])}")

    # HTML 파일 생성
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

    (RESULTS_DIR / "method_a.html").write_text(wrap_slides(a_slides, "Method A: Baseline"))
    (RESULTS_DIR / "method_e.html").write_text(wrap_slides(e_slides, "Method E: Layer Agents v2"))

    print(f"\n{'=' * 60}")
    print("완료! 비교:")
    print(f"  원본:     {RESULTS_DIR / 'original.html'}")
    print(f"  Method A: {RESULTS_DIR / 'method_a.html'}")
    print(f"  Method E: {RESULTS_DIR / 'method_e.html'}")


if __name__ == "__main__":
    main()
