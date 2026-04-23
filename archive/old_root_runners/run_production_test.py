#!/usr/bin/env python3
"""프로덕션 2-pass 방식으로 design_01 생성 테스트."""

import base64, json, re, sys, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI
client = OpenAI()

# 프로덕션 LAYOUT_SYSTEM_PROMPT 가져오기
sys.path.insert(0, str(Path(__file__).parent.parent / "ai_apis" / "ppt"))
from core.nodes.code_synthesizer import LAYOUT_SYSTEM_PROMPT, TEXT_INSERT_SYSTEM_PROMPT

DATA_DIR = Path(__file__).parent / "data" / "experiment_designs"
OUT = Path(__file__).parent / "results" / "production_test"
OUT.mkdir(parents=True, exist_ok=True)

with open(DATA_DIR / "meta.json") as f:
    meta = json.load(f)

style = meta["style"]
sc = meta["slides"][0]  # design_01_timeline
sid, stype = sc["id"], sc["type"]
content = sc["content"]

img_path = DATA_DIR / f"{sid}.png"
img_bytes = img_path.read_bytes()
b64 = base64.b64encode(img_bytes).decode()
header = base64.b64decode(b64[:16])
mime = "image/png" if header[:4] == b'\x89PNG' else "image/jpeg"

# content에서 speaker_script 등 제거
skip = {"speaker_script", "infographic_script"}
filtered = {k: v for k, v in content.items() if k not in skip}

# 구조 힌트
structure_lines = []
for k, v in filtered.items():
    if isinstance(v, list):
        if v and isinstance(v[0], dict):
            structure_lines.append(f"- {k}: 배열 ({len(v)}개), 각 항목 keys: {list(v[0].keys())}")
        else:
            structure_lines.append(f"- {k}: 배열 ({len(v)}개)")
    elif isinstance(v, dict):
        structure_lines.append(f"- {k}: 객체 (keys: {list(v.keys())})")
    else:
        structure_lines.append(f"- {k}: 단일 값")
structure_hint = "\n".join(structure_lines)

def extract_html(text):
    text = text.strip()
    fence = re.search(r"```(?:html)?\s*\n([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    else:
        text = re.sub(r"^```(?:html)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    html_start = re.search(r"<(?:style|div|section|!--)", text, re.IGNORECASE)
    if html_start and html_start.start() > 0:
        text = text[html_start.start():]
    return text.strip()

print(f"=== Production 2-Pass: {sid} ({stype}) ===")

# ── Pass 1: Layout ──
print("Pass 1 (Layout)...", end=" ", flush=True)
t0 = time.time()

pass1_prompt = f"""[슬라이드 정보]
slide_id: {sid}
type: {stype}

[테마 컬러]
primary: {style.get('primary_color', '#3B82F6')}
accent: {style.get('accent_color', '#60A5FA')}
background: {style.get('background', '#0F172A')}
text: {style.get('text_color', '#F1F5F9')}

[콘텐츠 구조 (반복 횟수 및 필드 참고용 — 텍스트 렌더링 금지)]
{structure_hint}

[디자인 이미지 첨부됨]
이 이미지의 시각적 구조(카드 배치, 아이콘, 색상, 간격, 장식)를 HTML + CSS로 정확히 재현하세요.
텍스트는 넣지 마세요 — 레이아웃 구조만 코드로 만드세요.

★ CSS 선택자는 .{sid} 로 스코핑하세요.
★ 컨테이너: <div class="slide-container {sid}">"""

resp1 = client.chat.completions.create(
    model="gpt-4o", max_tokens=16000,
    messages=[
        {"role": "system", "content": LAYOUT_SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            {"type": "text", "text": pass1_prompt},
        ]},
    ],
)
layout_html = extract_html(resp1.choices[0].message.content)
dt1 = time.time() - t0
print(f"{len(layout_html)} chars ({dt1:.0f}s)")

# ── Pass 2: Text Insertion ──
print("Pass 2 (Text)...", end=" ", flush=True)
t0 = time.time()

content_json = json.dumps(filtered, ensure_ascii=False, indent=2)
pass2_prompt = f"""[레이아웃 HTML — 구조를 유지하면서 텍스트를 삽입하세요]
```html
{layout_html}
```

[삽입할 콘텐츠 데이터]
{content_json}

[슬라이드 정보]
slide_id: {sid}
type: {stype}

위 HTML 레이아웃의 빈 영역에 콘텐츠 데이터의 실제 텍스트를 삽입하세요.
레이아웃 구조(CSS, 카드 배치, 색상)는 그대로 유지하고 텍스트와 아이콘만 추가하세요."""

resp2 = client.chat.completions.create(
    model="gpt-4o", max_tokens=16000,
    messages=[
        {"role": "system", "content": TEXT_INSERT_SYSTEM_PROMPT},
        {"role": "user", "content": pass2_prompt},
    ],
)
final_html = extract_html(resp2.choices[0].message.content)
dt2 = time.time() - t0
print(f"{len(final_html)} chars ({dt2:.0f}s)")

# ── 메트릭 ──
sys.path.insert(0, str(Path(__file__).parent))
from src.metrics.css_effect_preservation import css_richness
from src.metrics.content_completeness import content_completeness_rate

cr = css_richness(final_html)
ccr = content_completeness_rate(content, final_html)
print(f"\nCCR={ccr['rate']:.2f} CSS={cr['total_effects']} Colors={cr['unique_colors']}")
print(f"Detail: {cr['detail']}")
print(f"Total time: {dt1+dt2:.0f}s")

# ── 저장 + 스크린샷 ──
def wrap(h):
    return f'''<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;display:flex;justify-content:center;align-items:center;min-height:100vh;}}</style>
</head><body><div style="width:1280px;height:720px;overflow:hidden;position:relative;">{h}</div></body></html>'''

(OUT / "layout.html").write_text(wrap(layout_html))
(OUT / "final.html").write_text(wrap(final_html))

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 720})
    for name in ["layout", "final"]:
        pg.goto(f"file://{OUT / f'{name}.html'}")
        pg.wait_for_timeout(1500)
        pg.screenshot(path=str(OUT / f"{name}.png"))
    b.close()
print(f"\nSaved: {OUT}")
