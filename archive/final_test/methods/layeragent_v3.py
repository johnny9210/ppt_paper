"""LayerAgent v3 — Analyzer schema expansion + Hero Detail Agent.

v2 대비 추가:
1. Analyzer schema에 hero_blocks, title_bars, 확장 decoration 타입
2. Hero Detail Agent (bbox-highlighted full image) — hero 박스 전용
3. Assembler에서 hero HTML 포함
4. Text Inserter가 hero 영역 텍스트도 처리

여전히 DCGen-style bbox highlight (NOT crop).
"""
from __future__ import annotations

import json
import re

from langgraph.graph import StateGraph, START, END
from typing import TypedDict

from . import _common
from .bbox_utils import draw_bbox_on_image
from src.methods import crop_layer_agent as _la


# ════════════════════════════════════════════════════════════
# State v3 — hero_blocks 추가
# ════════════════════════════════════════════════════════════

class CropAgentStateV3(TypedDict, total=False):
    image_b64: str
    slide_id: str
    slide_type: str
    content: dict
    style: dict
    model: str

    analysis: dict
    card_crops_b64: list[str]

    bg_html: str

    card_htmls: list[str]
    card_positions: list[dict]
    hero_htmls: list[str]        # NEW
    hero_positions: list[dict]   # NEW

    content_html: str
    assembled_raw: str
    assembled: str


# ════════════════════════════════════════════════════════════
# Expanded Analyzer
# ════════════════════════════════════════════════════════════

ANALYSIS_PROMPT_V3 = """이 슬라이드 디자인 이미지(1280x720)를 분석하세요. 이미지 비율(0~1) 좌표로 위치를 알려주세요.

먼저 **layout_type** 판단:
- horizontal_row, grid, hub_spoke, pyramid, split, vertical_stack
- **split_hero_stats**: 한쪽에 큰 hero 박스 + 다른 쪽에 여러 stat 카드 (좌우 비대칭)
- **hero_only**: 단일 hero 박스 중심
- freeform

그다음 **요소 타입**을 모두 식별:

1. **hero_blocks**: 크고 standalone한 히어로 영역 (큰 플레이스홀더 숫자/제목, 두드러진 배경/테두리)
   - 예: 좌측 "XXXX" 골드 박스, 중앙 대형 통계 숫자, 메인 타이틀 박스
   - 카드보다 큰 영역이고 여러 카드가 주변에 배치되면 hero임

2. **cards**: 비슷한 크기로 반복되는 정보 블록 (같은 구조의 stat/step/feature 카드들)

3. **decorations**: 장식/구조 요소 — 더 넓게 분류
   - shape (triangle, circle, hexagon, diamond 등 기하 도형)
   - spotlight (상단/코너에서 오는 빛)
   - gradient_panel (배경의 큰 그라디언트 패널)
   - frame_accent (골드/네온 프레임 라인)
   - timeline_line, glow_node, connector, hub_circle (기존)

4. **background**: 전반적 배경
   - primary_color, secondary_color, accent_color (hex)
   - gradient_direction, has_pattern, pattern_type

JSON 형식으로:
```json
{
  "layout_type": "...",
  "global_palette": {
    "bg_primary": "#hex",
    "bg_secondary": "#hex",
    "accent": "#hex",
    "text_primary": "#hex",
    "text_accent": "#hex"
  },
  "aesthetic": "자유서술 (예: 'luxury dark gold with geometric decorations')",
  "hero_blocks": [
    {"id": "hero_1", "x1": 0.xx, "y1": 0.xx, "x2": 0.xx, "y2": 0.xx,
     "style_hint": "gold frame with XXXX placeholder and subtitle"}
  ],
  "cards": [
    {"id": "card_1", "x1": 0.xx, "y1": 0.xx, "x2": 0.xx, "y2": 0.xx}
  ],
  "decorations": [
    {"type": "shape", "subtype": "triangle", "x": 0.xx, "y": 0.xx, "size": 0.xx},
    {"type": "spotlight", "origin": "top-left", "color": "#hex"}
  ],
  "background": {
    "primary_color": "#hex",
    "gradient_direction": "135deg",
    "pattern_type": "geometric-mix"
  }
}
```

★ hero_blocks와 cards는 상호 배타적 — 한 요소는 둘 중 하나만
★ hero는 크기·독립성·타이포 중요도로 구분 (카드보다 크고 standalone)
★ 코드 아닌 JSON만 출력"""


def analyzer_v3(state: CropAgentStateV3) -> dict:
    model = state.get("model", "gpt-4o")
    raw = _la._vision_call(state["image_b64"], ANALYSIS_PROMPT_V3, model, max_tokens=2500)
    json_match = re.search(r"\{[\s\S]*\}", raw)
    try:
        analysis = json.loads(json_match.group(0))
    except Exception:
        analysis = {
            "layout_type": "horizontal_row",
            "global_palette": {},
            "aesthetic": "unknown",
            "hero_blocks": [],
            "cards": [
                {"id": f"card_{i+1}", "x1": round(0.04 + i * 0.24, 3), "y1": 0.30,
                 "x2": round(0.04 + i * 0.24 + 0.22, 3), "y2": 0.85}
                for i in range(4)
            ],
            "decorations": [],
            "background": {},
        }
    # v3는 crop 안 씀
    return {"analysis": analysis, "card_crops_b64": []}


# ════════════════════════════════════════════════════════════
# Card Detail Agent (v2와 동일 — bbox highlight)
# ════════════════════════════════════════════════════════════

CARD_DETAIL_PROMPT_V3 = """이 슬라이드 이미지에서 **빨간 사각형으로 표시된 카드 {card_idx}**를 HTML+CSS로 재현하세요.

★ Global context 활용 (빨간 네모 바깥도 관찰):
- 전체 팔레트: {palette_hint}
- Aesthetic: {aesthetic_hint}
- 다른 카드들과 일관된 스타일 유지 (전체 이미지에서 관찰)

★ 빨간 사각형 안만 묘사:
- 카드의 실제 재질, 테두리, 그림자, 내부 구획 정확히 재현
- 바깥 요소(다른 카드, hero, 배경)는 만들지 마세요

★★★ **정규화된 class 이름 필수** (카드 간 통일을 위해):
- 카드 컨테이너: `.card-{card_idx}`
- 아이콘 영역: **`.card-icon`** (다른 이름 쓰지 말 것 — .icon-placeholder, .icon-wrap 등 금지)
- 메인 값 영역: **`.card-value`** (큰 숫자/% — 다른 이름 금지)
- 라벨 영역: **`.card-label`** (작은 설명 — 다른 이름 금지)
- 내부 구조 표준화:
  ```
  <div class="card-{card_idx}">
    <div class="card-icon">아이콘자리</div>
    <div class="card-value">값자리</div>
    <div class="card-label">라벨자리</div>
  </div>
  ```

★ 크기 규약 (모든 카드 동일):
- 카드: width:100%; height:100%; position:relative;
- .card-icon: 높이 카드의 35% 이하, flex center
- .card-value: 높이 카드의 30% 정도, font-weight:800
- .card-label: 높이 카드의 25% 정도, font-weight:400

★ 텍스트 내용은 넣지 마세요 (나중에 Text Inserter가 채움)
★ 빨간 사각형 카드가 *가로형 long card* (아이콘 좌측 + 텍스트 우측) 이면:
  - display:flex; flex-direction:row; align-items:center;
  - .card-icon: flex:0 0 auto; width:20~25%;
  - .card-value + .card-label: 세로로 쌓되 우측에
★ *세로형 card* (아이콘 위 + 값 + 라벨) 이면:
  - display:flex; flex-direction:column; align-items:center; justify-content:center;

★ 출력: <style>과 <div>로만"""


def card_detail_agents_v3(state: CropAgentStateV3) -> dict:
    model = state.get("model", "gpt-4o")
    full = state["image_b64"]
    analysis = state.get("analysis", {})
    cards_meta = analysis.get("cards", [])
    palette = analysis.get("global_palette", {})
    aesthetic = analysis.get("aesthetic", "")
    palette_hint = ", ".join(f"{k}={v}" for k, v in palette.items() if v) or "(분석 못함)"

    card_htmls: list[str] = []
    card_positions: list[dict] = []
    for i, card in enumerate(cards_meta):
        bbox = (card.get("x1", 0), card.get("y1", 0), card.get("x2", 1), card.get("y2", 1))
        highlighted = draw_bbox_on_image(full, bbox, color=(255, 0, 0), width=6, label=f"CARD_{i+1}")
        prompt = CARD_DETAIL_PROMPT_V3.format(
            card_idx=i + 1, palette_hint=palette_hint, aesthetic_hint=aesthetic
        )
        raw = _la._vision_call(highlighted, prompt, model, max_tokens=6000)
        card_htmls.append(_la._extract_html(raw))
        card_positions.append({
            "card_id": f"card_{i+1}",
            "left": round(bbox[0] * 100, 1), "top": round(bbox[1] * 100, 1),
            "width": round((bbox[2] - bbox[0]) * 100, 1),
            "height": round((bbox[3] - bbox[1]) * 100, 1),
            "content_area": {
                "left": round(bbox[0] * 100 + 1.5, 1),
                "top": round(bbox[1] * 100 + 1.5, 1),
                "width": round((bbox[2] - bbox[0]) * 100 - 3, 1),
                "height": round((bbox[3] - bbox[1]) * 100 - 3, 1),
            },
        })
    return {"card_htmls": card_htmls, "card_positions": card_positions}


# ════════════════════════════════════════════════════════════
# HERO Detail Agent (NEW)
# ════════════════════════════════════════════════════════════

HERO_DETAIL_PROMPT = """이 슬라이드 이미지에서 **빨간 사각형으로 표시된 HERO 영역 {hero_idx}**를 HTML+CSS로 재현하세요.

★ Hero 영역이란:
- 큰 placeholder 숫자/제목이 있는 두드러진 standalone 박스
- 카드보다 크고 보통 슬라이드의 시각적 중심
- 강조 색상(골드/네온 등) 프레임이나 테두리 가질 수 있음

★ Global context:
- 전체 팔레트: {palette_hint}
- Aesthetic: {aesthetic_hint}

★ 빨간 사각형 안만 묘사:
- Hero 특유의 큰 타이포그래피 플레이스홀더 (예: "XXXX", "100%", "300K+")
- 프레임/테두리의 특수 색상 (골드 hairline 등)
- 서브타이틀 영역
- 내부 여백 / 정렬

★★★ **정규화된 class 이름 필수**:
- 컨테이너: `.hero-{hero_idx}`
- 메인 큰 값: **`.hero-value`** (예: "XXXX", "300%")
- 서브타이틀: **`.hero-subtitle`** (예: "Subtitle Placeholder")
- 다른 이름(.hero-placeholder, .value-big 등) 금지
- 구조:
  ```
  <div class="hero-{hero_idx}">
    <div class="hero-value">값자리</div>
    <div class="hero-subtitle">서브자리</div>
  </div>
  ```

★ 출력:
- 크기: width:100%; height:100%; position:relative; display:flex; flex-direction:column; align-items:center; justify-content:center;
- **텍스트 placeholder 넣기 OK** (나중에 Text Inserter가 실제 값으로 교체)
- <style>과 <div>로만"""


def hero_detail_agents(state: CropAgentStateV3) -> dict:
    model = state.get("model", "gpt-4o")
    full = state["image_b64"]
    analysis = state.get("analysis", {})
    heros = analysis.get("hero_blocks", [])
    palette = analysis.get("global_palette", {})
    aesthetic = analysis.get("aesthetic", "")
    palette_hint = ", ".join(f"{k}={v}" for k, v in palette.items() if v) or "(분석 못함)"

    hero_htmls: list[str] = []
    hero_positions: list[dict] = []
    for i, h in enumerate(heros):
        bbox = (h.get("x1", 0), h.get("y1", 0), h.get("x2", 1), h.get("y2", 1))
        highlighted = draw_bbox_on_image(full, bbox, color=(255, 0, 0), width=8, label=f"HERO_{i+1}")
        prompt = HERO_DETAIL_PROMPT.format(
            hero_idx=i + 1, palette_hint=palette_hint, aesthetic_hint=aesthetic
        )
        raw = _la._vision_call(highlighted, prompt, model, max_tokens=6000)
        hero_htmls.append(_la._extract_html(raw))
        hero_positions.append({
            "hero_id": f"hero_{i+1}",
            "left": round(bbox[0] * 100, 1), "top": round(bbox[1] * 100, 1),
            "width": round((bbox[2] - bbox[0]) * 100, 1),
            "height": round((bbox[3] - bbox[1]) * 100, 1),
        })
    return {"hero_htmls": hero_htmls, "hero_positions": hero_positions}


# ════════════════════════════════════════════════════════════
# Assembler v3 — hero + cards + bg
# ════════════════════════════════════════════════════════════

def assembler_v3(state: CropAgentStateV3) -> dict:
    sid = state["slide_id"]
    analysis = state.get("analysis", {})
    cards_meta = analysis.get("cards", [])
    heros_meta = analysis.get("hero_blocks", [])
    card_htmls = state.get("card_htmls", [])
    hero_htmls = state.get("hero_htmls", [])
    content = _la._filter_content(state.get("content", {}))

    elements = ""

    # Heroes (z-index 20)
    for i, html in enumerate(hero_htmls):
        if i >= len(heros_meta):
            break
        h = heros_meta[i]
        left = h.get("x1", 0) * 100
        top = h.get("y1", 0) * 100
        width = (h.get("x2", 1) - h.get("x1", 0)) * 100
        height = (h.get("y2", 1) - h.get("y1", 0)) * 100
        elements += f'<div class="hero-wrap-{i+1}" style="position:absolute;left:{left:.1f}%;top:{top:.1f}%;width:{width:.1f}%;height:{height:.1f}%;z-index:20;">\n{html}\n</div>\n'

    # Cards (z-index 10)
    for i, html in enumerate(card_htmls):
        if i >= len(cards_meta):
            break
        c = cards_meta[i]
        left = c.get("x1", 0) * 100
        top = c.get("y1", 0) * 100
        width = (c.get("x2", 1) - c.get("x1", 0)) * 100
        height = (c.get("y2", 1) - c.get("y1", 0)) * 100
        elements += f'<div class="card-wrap-{i+1}" style="position:absolute;left:{left:.1f}%;top:{top:.1f}%;width:{width:.1f}%;height:{height:.1f}%;z-index:10;">\n{html}\n</div>\n'

    # Title — hero가 있든 없든 상단 타이틀은 표시 (원본 reference와 일치)
    title = content.get("title", "")
    desc = content.get("description", "")
    title_div = ""
    if title:
        title_div = f"""<div style="position:absolute;left:50%;top:2.5%;transform:translateX(-50%);z-index:25;text-align:center;max-width:90%;">
    <div style="font-size:1.5rem;font-weight:800;color:#f1f5f9;text-shadow:0 2px 12px rgba(0,0,0,0.4);letter-spacing:0.02em;">{title}</div>
    {'<div style="font-size:0.7rem;color:rgba(148,163,184,0.7);margin-top:4px;">' + desc + '</div>' if desc else ''}
</div>"""

    assembled = f"""<div class="slide-container {sid}" style="width:1280px;height:720px;position:relative;overflow:hidden;font-family:'Noto Sans KR',sans-serif;">
    <div style="position:absolute;inset:0;z-index:0;">{state.get('bg_html', '')}</div>
    {elements}
    {title_div}
</div>"""
    return {"assembled_raw": assembled}


# ════════════════════════════════════════════════════════════
# Text Inserter v3 — hero 영역도 content.hero_value/title 채움
# ════════════════════════════════════════════════════════════

TEXT_INSERT_PROMPT_V3 = """아래 HTML은 슬라이드입니다. Hero와 Card 구조가 이미 완성되어 있습니다.
각 영역의 **빈 div**에 텍스트를 삽입하세요.

[현재 HTML]
```html
{html}
```

[삽입할 콘텐츠]
{content_json}

★★★ 핵심 규칙:
1. 기존 HTML의 CSS/구조는 그대로 유지 (style, class, position 절대 변경 X)
2. 빈 div 안에만 텍스트 삽입
3. 덮는 오버레이 만들지 마세요

★★★ Hero 영역 (.hero-1, .hero-2 등)이 있으면:
- content.hero_value, content.title, content.description 활용
- Hero의 큰 숫자/제목 placeholder를 실제 값으로 교체
- "XXXX" → 실제 값 (예: "300%"), 서브타이틀도 교체

★★★ Card 영역 (.card-1, .card-2 등):
- content.items/steps/metrics/stats/features 순서대로 매핑
- STEP/번호 라벨, 이모지, 제목, 설명 배치
- 카드 내부 빈 div에 삽입

★★★ 텍스트 색상은 **배경에 맞게 자연스럽게** (강제 색 금지):
- Hero 큰 숫자: 강조 색 사용 (global palette의 accent, 예: 골드면 골드)
- Card 제목: 밝은 대비 색
- Card 설명: 중간 대비 색

★ 전체 HTML 출력, <style>과 <div>만."""


def text_inserter_v3(state: CropAgentStateV3) -> dict:
    model = state.get("model", "gpt-4o")
    content = _la._filter_content(state.get("content", {}))
    html = state.get("assembled", "")
    content_json = json.dumps(content, ensure_ascii=False, indent=2)
    prompt = TEXT_INSERT_PROMPT_V3.format(html=html, content_json=content_json)
    raw = _la._text_call(prompt, model, max_tokens=16000)
    result = _la._extract_html(raw)
    if not result or len(result) < 100:
        return {"assembled": html}
    return {"assembled": result}


# ════════════════════════════════════════════════════════════
# Pipeline v3
# ════════════════════════════════════════════════════════════

def _maybe_hero(state: CropAgentStateV3) -> dict:
    """hero_blocks 없으면 빈 결과 반환 (skip)."""
    heros = state.get("analysis", {}).get("hero_blocks", [])
    if not heros:
        return {"hero_htmls": [], "hero_positions": []}
    return hero_detail_agents(state)


def build_pipeline_v3():
    g = StateGraph(CropAgentStateV3)
    g.add_node("analyzer", analyzer_v3)
    g.add_node("background_agent", _la.background_agent)
    g.add_node("card_detail_agents", card_detail_agents_v3)
    g.add_node("hero_detail_agents", _maybe_hero)
    g.add_node("assembler", assembler_v3)
    g.add_node("style_normalizer", _la.style_normalizer)
    g.add_node("text_inserter", text_inserter_v3)
    g.add_edge(START, "analyzer")
    g.add_edge("analyzer", "background_agent")
    g.add_edge("analyzer", "card_detail_agents")
    g.add_edge("analyzer", "hero_detail_agents")
    g.add_edge("background_agent", "assembler")
    g.add_edge("card_detail_agents", "assembler")
    g.add_edge("hero_detail_agents", "assembler")
    g.add_edge("assembler", "style_normalizer")
    g.add_edge("style_normalizer", "text_inserter")
    g.add_edge("text_inserter", END)
    return g.compile()


_pipeline = None

def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline_v3()
    return _pipeline


def run(slide_id: str, seed: int = 0, model: str = "gpt-4o") -> str:
    meta = _common.load_meta()
    design = _common.get_design_by_id(meta, slide_id)
    image_b64 = _common.b64_image(slide_id)
    pipeline = _get_pipeline()
    result = pipeline.invoke({
        "image_b64": image_b64,
        "slide_id": slide_id,
        "slide_type": design["type"],
        "content": design["content"],
        "style": meta["style"],
        "model": model,
    })
    return _common.extract_html(result.get("assembled", ""))
