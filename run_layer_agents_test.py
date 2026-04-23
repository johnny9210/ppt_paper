#!/usr/bin/env python3
"""Layer-Decomposed Multi-Agent 테스트 — 같은 Gemini 이미지로 원본과 비교."""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

import requests
from openai import OpenAI
from src.methods.layer_agents import generate as layer_generate

client = OpenAI()
RESULTS_DIR = Path(__file__).parent / "results" / "layer_agents"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TOPIC = "2025년 사이버보안 트렌드와 기업 대응 전략 발표자료. 랜섬웨어, 제로트러스트, AI 보안 위협을 다뤄줘. 다크 테마로 6장."


def main():
    print("=" * 60)
    print("Layer-Decomposed Multi-Agent Test")
    print("=" * 60)

    # AIDX PPT 생성
    print("\n[1] AIDX PPT 생성...", flush=True)
    resp = requests.post(
        "http://localhost:8012/api/generate",
        json={"user_request": TOPIC}, stream=True, timeout=600,
    )
    session_id = None
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        try:
            data = json.loads(line[5:].strip())
            if data.get("status") == "started": session_id = data["session_id"]
            if data.get("status") == "completed": break
        except: pass

    session = requests.get(f"http://localhost:8012/api/session/{session_id}").json()
    (RESULTS_DIR / "original.html").write_text(session.get("react_code", ""))
    print(f"  원본: {len(session.get('react_code', ''))} chars")

    # 디자인 이미지 + 콘텐츠
    slide_contents = session.get("slide_contents", [])
    style = session.get("research_brief", {}).get("style", {})
    design_images = {}
    for sd in session.get("slide_designs", []):
        sid = sd.get("slide_id", "")
        if sd.get("has_image"):
            img_resp = requests.get(f"http://localhost:8012/api/session/{session_id}/image/{sid}")
            if img_resp.status_code == 200:
                design_images[sid] = img_resp.json().get("image_b64", "")

    # Layer Agents 생성
    print(f"\n[2] Layer Agents 생성 ({len(slide_contents)} slides)...", flush=True)
    agent_slides = []

    for sc in slide_contents[:4]:
        sid = sc.get("slide_id", "")
        stype = sc.get("type", "")
        content = sc.get("content", {})
        img_b64 = design_images.get(sid, "")
        if not img_b64:
            continue

        print(f"\n  {sid} ({stype}):", flush=True)
        t0 = time.time()
        result = layer_generate(client, img_b64, sid, stype, content, style)
        elapsed = time.time() - t0

        agent_slides.append(result["assembled_html"])
        print(f"    bg: {len(result['bg_html'])} chars")
        print(f"    cards: {len(result['cards_html'])} chars")
        print(f"    content: {len(result['content_html'])} chars")
        print(f"    icons: {len(result['icons_html'])} chars")
        print(f"    assembled: {len(result['assembled_html'])} chars ({elapsed:.0f}s)")

    # HTML 조립
    slides_html = "\n".join(
        f'<div style="width:1280px;height:720px;margin:30px auto;box-shadow:0 20px 60px rgba(0,0,0,0.3);overflow:hidden;position:relative;">{s}</div>'
        for s in agent_slides
    )
    full_html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><title>Layer Agents</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;padding:40px;display:flex;flex-direction:column;align-items:center;gap:30px;}}</style>
</head><body>{slides_html}</body></html>"""

    (RESULTS_DIR / "layer_agents.html").write_text(full_html)
    print(f"\n  Layer Agents HTML: {len(full_html)} chars")
    print(f"\n완료!")


if __name__ == "__main__":
    main()
