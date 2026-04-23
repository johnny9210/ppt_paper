"""
CropLayerAgent: 크롭 기반 레이어 분해 멀티에이전트

핵심 개선:
1. 전체 이미지 → 구조 분석 + 배경/장식 생성
2. 각 카드 영역 크롭 → 개별 CSS 생성 (글래스모피즘 재현)
3. bbox 좌표 → 텍스트 배치 (text-only)
4. 기계적 합침

GPT-4o에서도 풍부한 CSS 재질(glassmorphism, neon glow)을 재현.
"""

import base64
import json
import re
from io import BytesIO
from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from openai import OpenAI
from PIL import Image


# ══════════════════════════════════════
# State
# ══════════════════════════════════════

class CropAgentState(TypedDict):
    image_b64: str
    slide_id: str
    slide_type: str
    content: dict
    style: dict
    model: str

    # Step 1
    analysis: dict
    card_crops_b64: list[str]  # 크롭된 카드 이미지 base64 목록

    # Step 2
    bg_html: str

    # Step 3
    card_htmls: list[str]
    card_positions: list[dict]

    # Step 4
    content_html: str

    # Step 5
    assembled_raw: str

    # Output
    assembled: str


# ══════════════════════════════════════
# Prompts
# ══════════════════════════════════════

SYSTEM_PROMPT = """당신은 디자인 이미지를 HTML+CSS로 변환하는 전문가입니다.
★ <style>과 <div>로 구성된 순수 HTML 코드만 출력하세요. 설명 없이.
★ CSS 효과를 최대한 풍부하게 사용: gradient, box-shadow, backdrop-filter, opacity, border-radius.
★ JavaScript 금지, <img> 금지."""

ANALYSIS_PROMPT = """이 디자인 이미지(1280x720 슬라이드)를 분석하세요. 이미지 비율(0~1)로 위치를 알려주세요.

먼저 이미지의 **레이아웃 타입**을 판단하세요:
- horizontal_row: 카드가 한 줄로 수평 배치
- grid: 카드가 2행 이상의 그리드
- hub_spoke: 중앙 허브 + 주변 카드 (방사형)
- pyramid: 위→아래로 점점 넓어지는 계층
- split: 좌우 분할
- vertical_stack: 카드가 세로로 쌓임
- freeform: 위 어느것에도 해당하지 않음

JSON으로 출력:
{
  "layout_type": "horizontal_row/grid/hub_spoke/pyramid/split/vertical_stack/freeform",
  "cards": [
    {"id": "card_1", "x1": 0.xx, "y1": 0.xx, "x2": 0.xx, "y2": 0.xx}
  ],
  "decorations": [
    {"type": "timeline_line/glow_node/connector/hub_circle", "description": "설명", "x": 0.xx, "y": 0.xx}
  ],
  "background": {"colors": ["#hex1", "#hex2"], "has_grid": true, "has_glow": true}
}

★★★ 카드 위치 규칙:
1. 이미지에서 보이는 카드의 **실제 위치를 정확히** 읽으세요
2. 같은 크기의 카드는 같은 width/height로
3. hub_spoke: 중앙 허브는 cards에 포함하지 말고 decorations에 넣으세요. 주변 카드만 cards에.
4. pyramid: 각 행의 카드 수가 다를 수 있음 (1-2-3 등)
5. 카드 사이에 여백을 적절히 남기세요

★ 장식(타임라인, 글로우 노드, 연결선, 허브 원 등)도 포함."""

BG_PROMPT = """이 디자인 이미지의 **배경 + 장식**을 HTML+CSS로 구현하세요.

[분석 참고]
{analysis_json}

구현할 것:
1. **메인 배경**: 이미지의 그라디언트를 정확히 (최소 2~3색)
2. **타임라인/연결 라인**: 네온 글로우 효과 (box-shadow: 0 0 15px + 0 0 30px)
3. **글로우 노드**: 카드 위/연결부에 발광 원 (radial-gradient + box-shadow 글로우)
4. **배경 글로우**: radial-gradient 대형 빛 2~3개
5. **도트/그리드 패턴**: 있으면 구현

★ 컨테이너: width:1280px; height:720px; position:relative;
★ 카드/텍스트는 만들지 마세요.
★ CSS 선택자: .{slide_id}-bg"""

CARD_DETAIL_PROMPT = """이 이미지는 슬라이드 카드 하나를 확대한 것입니다.
이 카드를 HTML+CSS로 최대한 정밀하게 재현하세요.

★ 반드시 구현할 CSS:
- backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
- background: rgba(적절한값, 0.3~0.5); (반투명!)
- border: 1px solid rgba(밝은색, 0.15~0.25);
- border-radius: 16~20px;
- box-shadow: 0 0 15px rgba(주색상, 0.15), 0 4px 20px rgba(0,0,0,0.3);

★ 이미지에서 보이는 내부 구분 영역도 재현:
- 각 영역에 border-radius + 약간 다른 rgba 배경

★ 카드 크기: width:100%; height:100%; position:relative;
★ CSS 선택자: .card-{card_idx}
★ 텍스트 넣지 마세요 (나중에 삽입됩니다)"""


TEXT_INSERT_PROMPT = """아래 HTML은 슬라이드입니다. 카드 구조가 이미 완성되어 있습니다.
각 카드의 **내부 빈 박스 안에** 텍스트를 삽입하세요.

[현재 HTML]
```html
{html}
```

[삽입할 콘텐츠]
{content_json}

★★★ 핵심 규칙:
1. 기존 HTML의 CSS/구조를 절대 변경하지 마세요 (style, class, position 등 그대로)
2. 각 카드 안에는 **빈 내부 div**(박스)가 있습니다 — 이 빈 div 안에 텍스트를 넣으세요
3. 카드 전체를 덮는 오버레이(position:absolute; inset:0)를 만들지 마세요!

★★★ 텍스트 삽입 방법:
- 카드 내부의 첫 번째 빈 div → STEP 라벨 + 이모지 + 제목 삽입
- 카드 내부의 두 번째 빈 div → 설명 텍스트 삽입
- 카드 내부의 세 번째 빈 div → 메트릭/추가 정보 (있으면)
- 빈 div 안에 텍스트를 직접 넣기: <div 기존속성>텍스트내용</div>

★★★ 텍스트 스타일:
- STEP 라벨: font-size:0.55rem; color:rgba(96,165,250,0.8); font-weight:600; letter-spacing:0.1em;
- 이모지: font-size:1.5rem;
- 제목: font-size:0.85rem; font-weight:700; color:#e2e8f0;
- 설명: font-size:0.65rem; color:rgba(148,163,184,0.85); line-height:1.4;
- 각 내부 div에: display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:8px;

★ 콘텐츠의 items/steps/columns를 순서대로 카드 1, 2, 3, 4...에 매핑
★ 전체 HTML을 출력
★ <style>과 <div>로만 출력"""

CONTENT_PROMPT = """슬라이드 텍스트를 배치하세요.

[카드 위치 (% 단위)]
{card_positions_json}

[삽입할 콘텐츠]
{content_json}

[슬라이드 타입: {slide_type}]

★★★ 텍스트 배치 구조 (각 카드 content_area 안에):

```
┌─────────────────────┐ ← content_area.top
│  STEP 01            │ ← 카드 상단 여백 안쪽, 작은 라벨
│                     │
│     🏛️              │ ← 이모지를 크게 (font-size:2rem)
│                     │
│  카드 제목           │ ← 볼드, 1rem
│                     │
│  설명 텍스트가       │ ← 0.75rem, muted color
│  여기에 들어감       │
│                     │
└─────────────────────┘ ← content_area.bottom
```

★★★ 배치 규칙:
1. STEP 라벨: content_area 상단에 배치. font-size:0.65rem; color:rgba(96,165,250,0.8); font-weight:600; letter-spacing:0.1em;
2. 이모지 아이콘: STEP 아래, 크게. font-size:1.8rem; margin:8px 0;
3. 카드 제목: 이모지 아래. font-size:0.95rem; font-weight:700; color:#e2e8f0;
4. 카드 설명: 제목 아래. font-size:0.72rem; color:rgba(148,163,184,0.85); line-height:1.5;
5. 전체를 **수직 중앙** 정렬: display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center;

★★★ 슬라이드 제목:
- 슬라이드 상단 중앙에 크게
- font-size:1.5rem; font-weight:800; color:#f1f5f9; text-shadow:0 2px 12px rgba(0,0,0,0.4);
- 부제: font-size:0.7rem; color:rgba(148,163,184,0.7); margin-top:6px;

★ 컨테이너: width:100%; height:100%; position:absolute; inset:0;
★ 모든 요소: position:absolute;
★ 각 카드의 텍스트 영역은 content_area 좌표 사용 + overflow:hidden;
★ 배경/카드 만들지 마세요. 텍스트만.
★ <style>과 <div>로만 출력"""


# ══════════════════════════════════════
# Utilities
# ══════════════════════════════════════

def _extract_html(text):
    text = text.strip()
    if "```html" in text: text = text.split("```html", 1)[1].split("```")[0]
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3: text = parts[1]
    start = re.search(r"<(?:style|div|!DOCTYPE)", text, re.IGNORECASE)
    if start and start.start() > 0: text = text[start.start():]
    return text.strip()


def _img_to_b64(img):
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _get_client():
    if not hasattr(_get_client, "_c"):
        _get_client._c = OpenAI()
    return _get_client._c


def _vision_call(image_b64, prompt, model="gpt-4o", max_tokens=10000):
    client = _get_client()
    header = base64.b64decode(image_b64[:16])
    mime = "image/png" if header[:4] == b'\x89PNG' else "image/jpeg"
    resp = client.chat.completions.create(
        model=model, max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ]},
        ],
    )
    return resp.choices[0].message.content


def _text_call(prompt, model="gpt-4o", max_tokens=8000):
    client = _get_client()
    resp = client.chat.completions.create(
        model=model, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def _filter_content(content):
    skip = {"speaker_script", "infographic_script"}
    return {k: v for k, v in content.items() if k not in skip}


# ══════════════════════════════════════
# Nodes
# ══════════════════════════════════════

def analyzer(state: CropAgentState) -> dict:
    """전체 이미지 → 구조 분석 + 카드 크롭 생성."""
    model = state.get("model", "gpt-4o")
    raw = _vision_call(state["image_b64"], ANALYSIS_PROMPT, model, max_tokens=2000)

    # JSON 파싱
    json_match = re.search(r'\{[\s\S]*\}', raw)
    try:
        analysis = json.loads(json_match.group(0))
    except:
        analysis = {"layout_type": "horizontal_row", "cards": [
            {"id": f"card_{i+1}", "x1": round(0.04+i*0.24, 3), "y1": 0.30, "x2": round(0.04+i*0.24+0.22, 3), "y2": 0.85}
            for i in range(4)
        ], "decorations": [], "background": {}}

    # 카드 크롭
    img_bytes = base64.b64decode(state["image_b64"])
    img = Image.open(BytesIO(img_bytes))
    w, h = img.size

    crops_b64 = []
    for card in analysis.get("cards", []):
        x1 = max(0, int(card.get("x1", 0) * w))
        y1 = max(0, int(card.get("y1", 0) * h))
        x2 = min(w, int(card.get("x2", 1) * w))
        y2 = min(h, int(card.get("y2", 1) * h))
        if x2 - x1 < 50 or y2 - y1 < 50:
            continue
        # 크롭 영역 약간 확장 (카드 주변 글로우 포함)
        pad = 10
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)
        cropped = img.crop((x1, y1, x2, y2))
        crops_b64.append(_img_to_b64(cropped))

    return {"analysis": analysis, "card_crops_b64": crops_b64}


def background_agent(state: CropAgentState) -> dict:
    """전체 이미지 → 배경 + 장식(라인, 노드, 글로우)."""
    model = state.get("model", "gpt-4o")
    analysis_json = json.dumps(state.get("analysis", {}), ensure_ascii=False, indent=2)
    prompt = BG_PROMPT.format(analysis_json=analysis_json, slide_id=state["slide_id"])
    raw = _vision_call(state["image_b64"], prompt, model, max_tokens=10000)
    return {"bg_html": _extract_html(raw)}


def card_detail_agents(state: CropAgentState) -> dict:
    """각 크롭 이미지 → 카드 CSS만 (텍스트 없음)."""
    model = state.get("model", "gpt-4o")
    crops = state.get("card_crops_b64", [])
    analysis = state.get("analysis", {})
    cards_meta = analysis.get("cards", [])

    card_htmls = []
    card_positions = []

    for i, crop_b64 in enumerate(crops):
        prompt = CARD_DETAIL_PROMPT.format(card_idx=i+1)
        raw = _vision_call(crop_b64, prompt, model, max_tokens=6000)
        card_htmls.append(_extract_html(raw))

        if i < len(cards_meta):
            c = cards_meta[i]
            card_positions.append({
                "card_id": f"card_{i+1}",
                "left": round(c.get("x1", 0) * 100, 1),
                "top": round(c.get("y1", 0) * 100, 1),
                "width": round((c.get("x2", 1) - c.get("x1", 0)) * 100, 1),
                "height": round((c.get("y2", 1) - c.get("y1", 0)) * 100, 1),
                "content_area": {
                    "left": round(c.get("x1", 0) * 100 + 1.5, 1),
                    "top": round(c.get("y1", 0) * 100 + 1.5, 1),
                    "width": round((c.get("x2", 1) - c.get("x1", 0)) * 100 - 3, 1),
                    "height": round((c.get("y2", 1) - c.get("y1", 0)) * 100 - 3, 1),
                },
            })

    return {"card_htmls": card_htmls, "card_positions": card_positions}


def content_agent(state: CropAgentState) -> dict:
    """콘텐츠 데이터에서 각 카드용 텍스트 HTML 조각을 생성."""
    content = _filter_content(state.get("content", {}))
    positions = state.get("card_positions", [])

    # 콘텐츠 항목 추출
    items = (content.get("items") or content.get("steps") or
             content.get("columns") or content.get("features") or
             content.get("phases") or content.get("metrics") or
             content.get("layers") or content.get("stats") or [])

    # 좌우 비교 타입
    if "left" in content and "right" in content:
        left = content["left"]
        right = content["right"]
        items = [
            {"emoji": "⬅️", "title": left.get("label", ""), "description": "\n".join(left.get("items", []))},
            {"emoji": "➡️", "title": right.get("label", ""), "description": "\n".join(right.get("items", []))},
        ]

    # 각 카드에 들어갈 텍스트 HTML 생성
    card_texts = []
    for i, item in enumerate(items):
        if i >= len(positions):
            break

        emoji = item.get("emoji", "")
        title = item.get("title", "")
        desc = item.get("description", "")[:100]
        step = item.get("step") or item.get("phase") or f"{i+1}"

        text_html = f"""<div style="position:absolute;inset:0;z-index:5;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:16px;overflow:hidden;">
    <div style="font-size:0.6rem;color:rgba(96,165,250,0.8);font-weight:600;letter-spacing:0.12em;margin-bottom:8px;">STEP {step}</div>
    <div style="font-size:1.8rem;margin-bottom:6px;">{emoji}</div>
    <div style="font-size:0.9rem;font-weight:700;color:#e2e8f0;margin-bottom:6px;">{title}</div>
    <div style="font-size:0.68rem;color:rgba(148,163,184,0.85);line-height:1.5;">{desc}</div>
</div>"""
        card_texts.append(text_html)

    # 슬라이드 제목 HTML (별도 배치)
    slide_title = content.get("title", "")
    slide_desc = content.get("description", "")
    title_html = f"""<div style="font-size:1.5rem;font-weight:800;color:#f1f5f9;text-shadow:0 2px 12px rgba(0,0,0,0.4);">{slide_title}</div>
<div style="font-size:0.7rem;color:rgba(148,163,184,0.7);margin-top:4px;">{slide_desc}</div>"""

    return {"content_html": json.dumps({"card_texts": card_texts, "title_html": title_html})}


NORMALIZE_PROMPT = """아래 HTML은 슬라이드의 카드들을 독립 생성 후 합친 것입니다.
카드마다 CSS 값이 미세하게 다릅니다. **CSS 값만 통일**해주세요.

```html
{html}
```

★★★ 수정 범위 — 이것만 변경:
- background의 rgba 알파값 → 모든 카드 동일하게 (0.15~0.25, 반투명!)
- border 색상/두께 → 모든 카드 동일 (1px solid rgba(148,163,184,0.15))
- border-radius → 모든 카드 16px
- box-shadow → 모든 카드 동일
- backdrop-filter → 모든 카드 blur(16px)

★★★ 절대 변경 금지 (이걸 바꾸면 레이아웃이 깨짐):
- position, left, top, width, height — 그대로 유지
- z-index — 그대로 유지
- div 구조 (추가/삭제/이동 금지)
- 텍스트 내용
- 배경 레이어 (z-index:0 영역)
- 인라인 style의 position/size 관련 속성

★ 입력 HTML의 구조를 그대로 유지하면서 CSS 속성 값만 통일하세요.
★ 전체 HTML을 출력하세요. <style>과 <div>만."""


def assembler(state: CropAgentState) -> dict:
    """카드(텍스트 없음)를 배치하고 제목 추가."""
    sid = state["slide_id"]
    analysis = state.get("analysis", {})
    cards_meta = analysis.get("cards", [])
    card_htmls = state.get("card_htmls", [])
    content = _filter_content(state.get("content", {}))

    card_positioned = ""
    for i, html in enumerate(card_htmls):
        if i >= len(cards_meta):
            break
        c = cards_meta[i]
        left = c.get("x1", 0) * 100
        top = c.get("y1", 0) * 100
        width = (c.get("x2", 1) - c.get("x1", 0)) * 100
        height = (c.get("y2", 1) - c.get("y1", 0)) * 100
        card_positioned += f'<div style="position:absolute;left:{left:.1f}%;top:{top:.1f}%;width:{width:.1f}%;height:{height:.1f}%;z-index:10;">\n{html}\n</div>\n'

    title = content.get("title", "")
    desc = content.get("description", "")
    title_div = f"""<div style="position:absolute;left:50%;top:3%;transform:translateX(-50%);z-index:25;text-align:center;">
    <div style="font-size:1.5rem;font-weight:800;color:#f1f5f9;text-shadow:0 2px 12px rgba(0,0,0,0.4);">{title}</div>
    <div style="font-size:0.7rem;color:rgba(148,163,184,0.7);margin-top:4px;">{desc}</div>
</div>"""

    assembled = f"""<div class="slide-container {sid}" style="width:1280px;height:720px;position:relative;overflow:hidden;font-family:'Noto Sans KR',sans-serif;">
    <div style="position:absolute;inset:0;z-index:0;">{state.get('bg_html', '')}</div>
    {card_positioned}
    {title_div}
</div>"""

    return {"assembled_raw": assembled}


def text_inserter(state: CropAgentState) -> dict:
    """완성된 HTML 구조에 텍스트만 삽입. 구조 변경 없이."""
    model = state.get("model", "gpt-4o")
    content = _filter_content(state.get("content", {}))
    html = state.get("assembled", "")  # normalizer 후의 HTML

    content_json = json.dumps(content, ensure_ascii=False, indent=2)
    prompt = TEXT_INSERT_PROMPT.format(html=html, content_json=content_json)

    raw = _text_call(prompt, model, max_tokens=16000)
    result = _extract_html(raw)

    if not result or len(result) < 100:
        return {"assembled": html}

    return {"assembled": result}


def style_normalizer(state: CropAgentState) -> dict:
    """HTML 코드를 읽고 카드 간 스타일 불일치를 통일."""
    model = state.get("model", "gpt-4o")
    html = state.get("assembled_raw", "")

    prompt = NORMALIZE_PROMPT.format(html=html)
    raw = _text_call(prompt, model, max_tokens=16000)
    normalized = _extract_html(raw)

    if not normalized or len(normalized) < 100:
        return {"assembled": html}

    return {"assembled": normalized}


# ══════════════════════════════════════
# Pipeline
# ══════════════════════════════════════

def build_pipeline():
    """
    analyzer (전체 분석 + 크롭)
      ├→ background_agent (전체 이미지 → 배경+장식)
      └→ card_detail_agents (크롭 → 개별 카드 CSS)
           └→ content_agent (text-only, 카드 위치 기반)
                └→ assembler → style_normalizer → END
    """
    graph = StateGraph(CropAgentState)

    graph.add_node("analyzer", analyzer)
    graph.add_node("background_agent", background_agent)
    graph.add_node("card_detail_agents", card_detail_agents)
    graph.add_node("assembler", assembler)
    graph.add_node("style_normalizer", style_normalizer)
    graph.add_node("text_inserter", text_inserter)

    graph.add_edge(START, "analyzer")
    graph.add_edge("analyzer", "background_agent")
    graph.add_edge("analyzer", "card_detail_agents")

    graph.add_edge("background_agent", "assembler")
    graph.add_edge("card_detail_agents", "assembler")

    graph.add_edge("assembler", "style_normalizer")
    graph.add_edge("style_normalizer", "text_inserter")
    graph.add_edge("text_inserter", END)

    return graph.compile()


_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


# ══════════════════════════════════════
# Public API
# ══════════════════════════════════════

def generate_from_saved_image(
    image_path: str,
    slide_id: str,
    slide_type: str,
    content: dict,
    style: dict,
    model: str = "gpt-4o",
) -> dict:
    img_bytes = Path(image_path).read_bytes()
    b64 = base64.b64encode(img_bytes).decode()

    pipeline = get_pipeline()
    result = pipeline.invoke({
        "image_b64": b64,
        "slide_id": slide_id,
        "slide_type": slide_type,
        "content": content,
        "style": style,
        "model": model,
    })

    return {
        "analysis": result.get("analysis", {}),
        "card_positions": result.get("card_positions", []),
        "assembled": result.get("assembled", ""),
    }
