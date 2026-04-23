#!/usr/bin/env python3
"""크롭 기반 LayerAgent 테스트: 전체구조 + 개별요소 크롭 → 합침."""

import base64, json, re, sys, time
from pathlib import Path
from PIL import Image
from io import BytesIO

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI
client = OpenAI()

DATA_DIR = Path(__file__).parent / "data" / "experiment_designs"
OUT = Path(__file__).parent / "results" / "crop_agent_test"
OUT.mkdir(parents=True, exist_ok=True)


def call_vision(image_b64, prompt, max_tokens=8000):
    header = base64.b64decode(image_b64[:16])
    mime = "image/png" if header[:4] == b'\x89PNG' else "image/jpeg"
    resp = client.chat.completions.create(
        model="gpt-4o", max_tokens=max_tokens,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
            {"type": "text", "text": prompt},
        ]}],
    )
    return resp.choices[0].message.content


def call_text(prompt, max_tokens=8000):
    resp = client.chat.completions.create(
        model="gpt-4o", max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def extract_html(text):
    text = text.strip()
    if "```html" in text:
        text = text.split("```html", 1)[1].split("```")[0]
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3: text = parts[1]
    start = re.search(r"<(?:style|div|!DOCTYPE)", text, re.IGNORECASE)
    if start and start.start() > 0: text = text[start.start():]
    return text.strip()


def img_to_b64(img):
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


with open(DATA_DIR / "meta.json") as f:
    meta = json.load(f)

style = meta["style"]
sc = meta["slides"][0]  # design_01_timeline
sid, stype = sc["id"], sc["type"]
content = sc["content"]
skip = {"speaker_script", "infographic_script"}
filtered = {k: v for k, v in content.items() if k not in skip}

img = Image.open(DATA_DIR / f"{sid}.png")
full_b64 = base64.b64encode((DATA_DIR / f"{sid}.png").read_bytes()).decode()
w, h = img.size

print(f"=== Crop-Based Agent: {sid} ({stype}) ===")
print(f"Image: {w}x{h}")
t_start = time.time()

# ══════════════════════════════════════
# Step 1: 전체 구조 분석 → 카드 위치 파악
# ══════════════════════════════════════
print("\n[Step 1] 전체 구조 분석...", end=" ", flush=True)
t0 = time.time()

analysis_prompt = """이 슬라이드 디자인 이미지(1280x720)를 분석하세요.

각 카드/요소의 위치를 이미지 비율(0~1)로 알려주세요:

JSON으로 출력:
{
  "background": {"type": "dark_gradient", "colors": ["#hex1", "#hex2"]},
  "cards": [
    {"id": "card_1", "x1": 0.02, "y1": 0.35, "x2": 0.27, "y2": 0.85, "description": "첫번째 글래스 카드"},
    ...
  ],
  "decorations": [
    {"type": "timeline_line", "x1": 0.05, "y1": 0.38, "x2": 0.95, "y2": 0.38}
  ]
}"""

analysis_raw = call_vision(full_b64, analysis_prompt, max_tokens=2000)
print(f"({time.time()-t0:.0f}s)")

# JSON 파싱
json_match = re.search(r'\{[\s\S]*\}', analysis_raw)
if json_match:
    try:
        analysis = json.loads(json_match.group(0))
    except:
        analysis = {"cards": [
            {"id": "card_1", "x1": 0.02, "y1": 0.35, "x2": 0.27, "y2": 0.85},
            {"id": "card_2", "x1": 0.27, "y1": 0.35, "x2": 0.50, "y2": 0.85},
            {"id": "card_3", "x1": 0.50, "y1": 0.35, "x2": 0.73, "y2": 0.85},
            {"id": "card_4", "x1": 0.73, "y1": 0.35, "x2": 0.98, "y2": 0.85},
        ]}
else:
    analysis = {"cards": [
        {"id": "card_1", "x1": 0.02, "y1": 0.35, "x2": 0.27, "y2": 0.85},
        {"id": "card_2", "x1": 0.27, "y1": 0.35, "x2": 0.50, "y2": 0.85},
        {"id": "card_3", "x1": 0.50, "y1": 0.35, "x2": 0.73, "y2": 0.85},
        {"id": "card_4", "x1": 0.73, "y1": 0.35, "x2": 0.98, "y2": 0.85},
    ]}

cards = analysis.get("cards", [])
print(f"  카드 {len(cards)}개 감지")

# ══════════════════════════════════════
# Step 2: 배경 생성 (전체 이미지)
# ══════════════════════════════════════
print("[Step 2] 배경 생성...", end=" ", flush=True)
t0 = time.time()

bg_html = extract_html(call_vision(full_b64, """이 디자인 이미지의 배경만 HTML+CSS로 구현하세요.

배경 요소만: 그라디언트, 글로우, 도트 패턴, 장식 라인, 타임라인 라인 등.
카드/텍스트/아이콘은 만들지 마세요.

★ 컨테이너: width:1280px; height:720px; position:relative;
★ <style>과 <div>로만 출력 (설명 없이)""", max_tokens=6000))
print(f"{len(bg_html)} chars ({time.time()-t0:.0f}s)")

# ══════════════════════════════════════
# Step 3: 각 카드 크롭 → 개별 CSS 생성
# ══════════════════════════════════════
card_htmls = []
for i, card in enumerate(cards):
    x1 = int(card.get("x1", 0) * w)
    y1 = int(card.get("y1", 0) * h)
    x2 = int(card.get("x2", 1) * w)
    y2 = int(card.get("y2", 1) * h)
    
    # 크롭
    cropped = img.crop((x1, y1, x2, y2))
    crop_b64 = img_to_b64(cropped)
    
    print(f"[Step 3-{i+1}] 카드 {i+1} 크롭({x1},{y1}→{x2},{y2})...", end=" ", flush=True)
    t0 = time.time()
    
    card_prompt = f"""이 이미지는 슬라이드의 카드 하나를 확대한 것입니다.
이 카드를 HTML+CSS로 최대한 정밀하게 재현하세요.

★ 시각적 특성을 모두 CSS로 표현:
- 반투명 배경: backdrop-filter:blur(16px); background:rgba(적절한값);
- 테두리 글로우: border + box-shadow로 네온 효과
- 내부 구분 영역: 이미지에서 보이는 섹션 구분 그대로
- 빛 반사/하이라이트: 있으면 linear-gradient로
- 모서리: border-radius

★ 카드 크기: width:100%; height:100%; position:absolute; inset:0;
★ <style>과 <div>로만 출력
★ CSS 선택자: .card-{i+1}
★ JavaScript 금지, <img> 금지, 텍스트 넣지 마세요"""
    
    card_html = extract_html(call_vision(crop_b64, card_prompt, max_tokens=4000))
    card_htmls.append({"html": card_html, "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    print(f"{len(card_html)} chars ({time.time()-t0:.0f}s)")

# ══════════════════════════════════════
# Step 4: 텍스트 삽입
# ══════════════════════════════════════
print("[Step 4] 텍스트 생성...", end=" ", flush=True)
t0 = time.time()

items = filtered.get("items", filtered.get("steps", []))
content_parts = []
for i, item in enumerate(items):
    if i >= len(cards): break
    card = cards[i]
    left_pct = card.get("x1", 0) * 100 + 2
    top_pct = card.get("y1", 0) * 100 + 2
    w_pct = (card.get("x2", 1) - card.get("x1", 0)) * 100 - 4
    h_pct = (card.get("y2", 1) - card.get("y1", 0)) * 100 - 4
    
    emoji = item.get("emoji", "")
    title = item.get("title", "")
    desc = item.get("description", "")[:80]
    
    content_parts.append(f"""<div style="position:absolute;left:{left_pct}%;top:{top_pct}%;width:{w_pct}%;height:{h_pct}%;z-index:20;padding:12px;overflow:hidden;">
    <div style="font-size:0.7rem;color:rgba(96,165,250,0.7);font-weight:600;letter-spacing:0.1em;margin-bottom:8px;">STEP {i+1}</div>
    <div style="font-size:1.1rem;margin-bottom:6px;">{emoji} <strong style="color:#e2e8f0;">{title}</strong></div>
    <div style="font-size:0.75rem;color:rgba(148,163,184,0.8);line-height:1.5;">{desc}</div>
</div>""")

content_html = "\n".join(content_parts)
print(f"{len(content_html)} chars ({time.time()-t0:.0f}s)")

# 제목
title = filtered.get("title", "")
description = filtered.get("description", "")
title_html = f"""<div style="position:absolute;left:5%;top:4%;z-index:20;">
    <div style="font-size:1.8rem;font-weight:800;color:#f1f5f9;letter-spacing:-0.02em;text-shadow:0 2px 10px rgba(0,0,0,0.3);">{title}</div>
    <div style="font-size:0.85rem;color:rgba(148,163,184,0.8);margin-top:6px;">{description}</div>
</div>"""

# ══════════════════════════════════════
# Step 5: 조립
# ══════════════════════════════════════
card_positioned = ""
for i, cd in enumerate(card_htmls):
    left_pct = cd["x1"] / w * 100
    top_pct = cd["y1"] / h * 100
    w_pct = (cd["x2"] - cd["x1"]) / w * 100
    h_pct = (cd["y2"] - cd["y1"]) / h * 100
    card_positioned += f"""<div style="position:absolute;left:{left_pct:.1f}%;top:{top_pct:.1f}%;width:{w_pct:.1f}%;height:{h_pct:.1f}%;z-index:10;">
    {cd["html"]}
</div>\n"""

assembled = f"""<div class="slide-container {sid}" style="width:1280px;height:720px;position:relative;overflow:hidden;font-family:'Noto Sans KR',sans-serif;">
    <div style="position:absolute;inset:0;z-index:0;">{bg_html}</div>
    {card_positioned}
    {title_html}
    {content_html}
</div>"""

total_time = time.time() - t_start
print(f"\n총 시간: {total_time:.0f}s | HTML: {len(assembled)} chars")

# 메트릭
from src.metrics.css_effect_preservation import css_richness
from src.metrics.content_completeness import content_completeness_rate
cr = css_richness(assembled)
ccr = content_completeness_rate(content, assembled)
print(f"CCR={ccr['rate']:.2f} CSS={cr['total_effects']} Colors={cr['unique_colors']}")
print(f"Detail: {cr['detail']}")

# 저장 + 스크린샷
wrap = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;display:flex;justify-content:center;align-items:center;min-height:100vh;}}</style>
</head><body>{assembled}</body></html>"""

(OUT / "crop_agent.html").write_text(wrap)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1280,"height":720})
    pg.goto(f"file://{OUT}/crop_agent.html")
    pg.wait_for_timeout(2000)
    pg.screenshot(path=str(OUT / "crop_agent.png"))
    b.close()
print(f"Saved: {OUT}")
