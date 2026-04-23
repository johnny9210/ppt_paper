#!/usr/bin/env python3
"""크롭 기반 LayerAgent v2: 배경+장식 강화, 크롭 좌표 정밀화."""

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
OUT = Path(__file__).parent / "results" / "crop_agent_v2"
OUT.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """당신은 디자인 이미지를 HTML+CSS로 변환하는 전문가입니다.
★ <style>과 <div>로 구성된 순수 HTML 코드만 출력하세요. 설명 없이.
★ CSS 효과를 최대한 풍부하게 사용하세요: gradient, box-shadow, backdrop-filter, opacity, border-radius, transform.
★ JavaScript 금지, <img> 금지."""


def call_vision(image_b64, prompt, max_tokens=10000):
    header = base64.b64decode(image_b64[:16])
    mime = "image/png" if header[:4] == b'\x89PNG' else "image/jpeg"
    resp = client.chat.completions.create(
        model="gpt-4o", max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ]},
        ],
    )
    return resp.choices[0].message.content


def extract_html(text):
    text = text.strip()
    if "```html" in text: text = text.split("```html", 1)[1].split("```")[0]
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
sid = sc["id"]
content = sc["content"]
skip = {"speaker_script", "infographic_script"}
filtered = {k: v for k, v in content.items() if k not in skip}

img = Image.open(DATA_DIR / f"{sid}.png")
full_b64 = base64.b64encode((DATA_DIR / f"{sid}.png").read_bytes()).decode()
w, h = img.size

print(f"=== Crop Agent v2: {sid} ===")
t_start = time.time()

# ══════════════════════════════════════
# Step 1: 전체 구조 분석 → 정밀 카드 좌표
# ══════════════════════════════════════
print("[1] 구조 분석...", end=" ", flush=True)
t0 = time.time()

analysis_raw = call_vision(full_b64, """이 디자인 이미지(1376x768)를 정밀 분석하세요.

각 요소의 위치를 이미지 비율(0~1)로 정확히 알려주세요.

JSON으로 출력:
{
  "cards": [
    {"id": "card_1", "x1": 0.xx, "y1": 0.xx, "x2": 0.xx, "y2": 0.xx},
    ...
  ],
  "decorations": [
    {"type": "timeline_line", "y_position": 0.xx, "color": "#hex"},
    {"type": "glow_node", "x": 0.xx, "y": 0.xx, "color": "#hex"},
    ...
  ],
  "background_colors": ["#hex1", "#hex2", "#hex3"]
}

★ 카드 4개의 위치를 정확히. 카드 크기가 서로 비슷해야 합니다.
★ 타임라인 라인, 글로우 노드 등 장식 요소도 포함.""", max_tokens=2000)

json_match = re.search(r'\{[\s\S]*\}', analysis_raw)
try:
    analysis = json.loads(json_match.group(0))
except:
    analysis = {"cards": [
        {"id": f"card_{i+1}", "x1": 0.05+i*0.235, "y1": 0.42, "x2": 0.05+(i+1)*0.235-0.01, "y2": 0.82}
        for i in range(4)
    ], "decorations": [], "background_colors": ["#0a0e1a", "#162040", "#1a1f3a"]}

cards = analysis.get("cards", [])
decorations = analysis.get("decorations", [])
bg_colors = analysis.get("background_colors", ["#0a0e1a", "#162040"])
print(f"카드 {len(cards)}개, 장식 {len(decorations)}개 ({time.time()-t0:.0f}s)")

# ══════════════════════════════════════
# Step 2: 배경 + 타임라인 + 글로우 (전체 이미지)
# ══════════════════════════════════════
print("[2] 배경+장식...", end=" ", flush=True)
t0 = time.time()

deco_desc = json.dumps(decorations, ensure_ascii=False) if decorations else "타임라인 라인 + 글로우 노드"

bg_html = extract_html(call_vision(full_b64, f"""이 디자인 이미지의 **배경 + 장식 요소**를 HTML+CSS로 구현하세요.

구현할 것:
1. **메인 배경**: 다크 그라디언트 (이미지의 정확한 색상 사용)
   - background: linear-gradient(방향, 색1, 색2, 색3);
   
2. **타임라인 라인**: 이미지 중간을 가로지르는 네온 글로우 라인
   - 시안→퍼플 그라디언트, box-shadow로 글로우 효과
   - height: 2~3px, 양쪽으로 글로우: box-shadow: 0 0 15px rgba(color, 0.5);
   
3. **글로우 노드**: 타임라인 위 발광하는 원 4개
   - 각 카드 위에 하나씩, border-radius:50%
   - 중심: 밝은 색, 주변: radial-gradient 글로우
   - box-shadow: 0 0 20px rgba(color, 0.6), 0 0 40px rgba(color, 0.3);
   
4. **배경 도트/그리드 패턴**
5. **배경 글로우**: radial-gradient로 부드러운 빛 2~3개

장식 참고: {deco_desc}
배경색 참고: {json.dumps(bg_colors)}

★ 컨테이너: width:1280px; height:720px; position:relative;
★ 카드/텍스트는 만들지 마세요. 배경+라인+노드만.""", max_tokens=10000))
print(f"{len(bg_html)} chars ({time.time()-t0:.0f}s)")

# ══════════════════════════════════════
# Step 3: 각 카드 크롭 → 개별 CSS
# ══════════════════════════════════════
card_htmls = []
for i, card in enumerate(cards[:4]):
    x1 = max(0, int(card.get("x1", 0) * w))
    y1 = max(0, int(card.get("y1", 0) * h))
    x2 = min(w, int(card.get("x2", 1) * w))
    y2 = min(h, int(card.get("y2", 1) * h))
    
    if x2 - x1 < 50 or y2 - y1 < 50:
        x1, y1 = int(0.05*w + i*0.235*w), int(0.42*h)
        x2, y2 = int(x1 + 0.22*w), int(0.82*h)
    
    cropped = img.crop((x1, y1, x2, y2))
    crop_b64 = img_to_b64(cropped)
    
    print(f"[3-{i+1}] 카드 {i+1}...", end=" ", flush=True)
    t0 = time.time()
    
    card_html = extract_html(call_vision(crop_b64, f"""이 이미지는 슬라이드 카드 하나를 확대한 것입니다.
이 카드를 HTML+CSS로 최대한 정밀하게 재현하세요.

★ 반드시 구현할 CSS:
- backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
- background: rgba(적절한값, 0.3~0.5); (반투명!)
- border: 1px solid rgba(밝은색, 0.15~0.25);
- border-radius: 16~20px;
- box-shadow: 0 0 15px rgba(주색상, 0.15), 0 4px 20px rgba(0,0,0,0.3);

★ 이미지에서 보이는 내부 구분 영역도 재현:
- 상단 영역, 하단 그리드 등을 div로 구분
- 각 영역에 border-radius + 약간 다른 rgba 배경

★ 카드 크기: width:100%; height:100%; position:relative;
★ CSS 선택자: .card-{i+1}
★ 텍스트 넣지 마세요""", max_tokens=6000))
    
    card_htmls.append({"html": card_html, "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    print(f"{len(card_html)} chars ({time.time()-t0:.0f}s)")

# ══════════════════════════════════════
# Step 4: 텍스트
# ══════════════════════════════════════
print("[4] 텍스트...", end=" ", flush=True)

items = filtered.get("items", filtered.get("steps", []))
content_parts = []

# STEP 라벨 (카드 위에)
for i, card in enumerate(cards[:4]):
    cx = (card.get("x1",0) + card.get("x2",1)) / 2 * 100
    top = card.get("y1", 0.42) * 100 - 5
    content_parts.append(f"""<div style="position:absolute;left:{cx-3}%;top:{top}%;z-index:25;font-size:0.6rem;color:rgba(148,163,184,0.6);font-weight:600;letter-spacing:0.12em;">STEP 0{i+1}</div>""")

# 카드 내 텍스트
for i, item in enumerate(items[:4]):
    if i >= len(cards): break
    card = cards[i]
    left_pct = card.get("x1", 0) * 100 + 1.5
    top_pct = card.get("y1", 0) * 100 + 1.5
    w_pct = (card.get("x2", 1) - card.get("x1", 0)) * 100 - 3
    h_pct = (card.get("y2", 1) - card.get("y1", 0)) * 100 - 3
    
    emoji = item.get("emoji", "")
    title = item.get("title", "")
    desc = item.get("description", "")[:70]
    
    content_parts.append(f"""<div style="position:absolute;left:{left_pct}%;top:{top_pct}%;width:{w_pct}%;height:{h_pct}%;z-index:20;padding:14px;overflow:hidden;display:flex;flex-direction:column;justify-content:center;">
    <div style="font-size:1rem;font-weight:700;color:#e2e8f0;margin-bottom:8px;">{emoji} {title}</div>
    <div style="font-size:0.72rem;color:rgba(148,163,184,0.85);line-height:1.55;">{desc}</div>
</div>""")

# 제목
title = filtered.get("title", "")
description = filtered.get("description", "")
title_html = f"""<div style="position:absolute;left:50%;top:3%;transform:translateX(-50%);z-index:25;text-align:center;">
    <div style="font-size:1.6rem;font-weight:800;color:#f1f5f9;letter-spacing:-0.02em;text-shadow:0 2px 12px rgba(0,0,0,0.4);">{title}</div>
    <div style="font-size:0.75rem;color:rgba(148,163,184,0.7);margin-top:6px;">{description}</div>
</div>"""

content_html = "\n".join(content_parts)
print(f"{len(content_html)+len(title_html)} chars")

# ══════════════════════════════════════
# Step 5: 조립
# ══════════════════════════════════════
card_positioned = ""
for i, cd in enumerate(card_htmls):
    left_pct = cd["x1"] / w * 100
    top_pct = cd["y1"] / h * 100
    w_pct = (cd["x2"] - cd["x1"]) / w * 100
    h_pct = (cd["y2"] - cd["y1"]) / h * 100
    card_positioned += f'<div style="position:absolute;left:{left_pct:.1f}%;top:{top_pct:.1f}%;width:{w_pct:.1f}%;height:{h_pct:.1f}%;z-index:10;">\n{cd["html"]}\n</div>\n'

assembled = f"""<div class="slide-container {sid}" style="width:1280px;height:720px;position:relative;overflow:hidden;font-family:'Noto Sans KR',sans-serif;">
    <div style="position:absolute;inset:0;z-index:0;">{bg_html}</div>
    {card_positioned}
    {title_html}
    {content_html}
</div>"""

total_time = time.time() - t_start
print(f"\n총: {total_time:.0f}s | HTML: {len(assembled)} chars")

from src.metrics.css_effect_preservation import css_richness
from src.metrics.content_completeness import content_completeness_rate
cr = css_richness(assembled)
ccr = content_completeness_rate(content, assembled)
print(f"CCR={ccr['rate']:.2f} CSS={cr['total_effects']} Colors={cr['unique_colors']}")
print(f"Detail: {cr['detail']}")

wrap = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;display:flex;justify-content:center;align-items:center;min-height:100vh;}}</style>
</head><body>{assembled}</body></html>"""

(OUT / "result.html").write_text(wrap)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1280,"height":720})
    pg.goto(f"file://{OUT}/result.html")
    pg.wait_for_timeout(2000)
    pg.screenshot(path=str(OUT / "result.png"))
    b.close()
print(f"Saved: {OUT}")
