"""LayerAgent v9 — Connection lines + Background patterns + Hub enhancement.

v8 대비 추가:
1. Hub-spoke 감지 시 허브↔카드 bezier 연결선 SVG 자동 생성
2. Aesthetic에 맞는 배경 패턴 주입 (circuit/topographic/dot/hex)
3. 중앙 허브 강조 (큰 글로우, 프레임, 아이콘)

나머지 v8 구성요소 (Icon library, Shape library, Design Director, BG 3-split) 모두 재사용.
"""
from __future__ import annotations

import re

from langgraph.graph import StateGraph, START, END

from . import _common
from .icon_agent import icon_agent_node
from .icon_library import shape_html
from .pattern_library import (
    render_connections,
    background_pattern,
    pattern_for_aesthetic,
    hub_enhancement_html,
)
from .layeragent_v5 import (
    StateV5,
    analyzer_v3,
    design_director,
    base_bg_agent,
    atmosphere_agent,
    decoration_agent,
    card_detail_agents_v5,
    hero_detail_agents_v5,
)
from .layeragent_v3 import text_inserter_v3
from src.methods import crop_layer_agent as _la


def _card_center(card: dict) -> tuple[float, float]:
    x = (card.get("x1", 0) + card.get("x2", 1)) / 2 * 100
    y = (card.get("y1", 0) + card.get("y2", 1)) / 2 * 100
    return (x, y)


def _ensure_text_visible(html: str) -> str:
    """Card Detail Agent가 .card-value / .card-label 에 display:none 걸 때 복구.

    이유: 원본 이미지가 placeholder 텍스트 없는 icon-only 카드면 agent가
    "텍스트 자리 필요 없음" 으로 판단. 하지만 우리 콘텐츠에는 텍스트가 있음.
    """
    # .card-value { ... display: none; ... } 같은 패턴을 display: flex 로
    html = re.sub(
        r'(\.card-(?:value|label|icon)\s*\{[^}]*?)display\s*:\s*none\s*;?',
        r'\1',
        html, flags=re.IGNORECASE,
    )
    # hero-value / hero-subtitle 도 동일 처리
    html = re.sub(
        r'(\.hero-(?:value|subtitle)\s*\{[^}]*?)display\s*:\s*none\s*;?',
        r'\1',
        html, flags=re.IGNORECASE,
    )
    return html


def _hub_center_from_analysis(analysis: dict) -> tuple[float, float] | None:
    """Analyzer 결과에서 hub 중심 위치 추정.

    우선순위:
    1. hero_blocks[0] 중심
    2. decorations 중 type=='hub_circle' 또는 'spotlight'
    3. 카드들의 bbox 중심 평균
    """
    heros = analysis.get("hero_blocks", [])
    if heros:
        h = heros[0]
        return (
            (h.get("x1", 0) + h.get("x2", 1)) / 2 * 100,
            (h.get("y1", 0) + h.get("y2", 1)) / 2 * 100,
        )
    for d in analysis.get("decorations", []):
        if d.get("type") in ("hub_circle", "hub", "spotlight"):
            return (d.get("x", 0.5) * 100, d.get("y", 0.5) * 100)
    cards = analysis.get("cards", [])
    if cards:
        xs = [(c.get("x1", 0) + c.get("x2", 1)) / 2 for c in cards]
        ys = [(c.get("y1", 0) + c.get("y2", 1)) / 2 for c in cards]
        return (sum(xs) / len(xs) * 100, sum(ys) / len(ys) * 100)
    return None


# ════════════════════════════════════════════════════════════
# Assembler v9 — patterns + connections + hub enhancement
# ════════════════════════════════════════════════════════════

def assembler_v9(state) -> dict:
    sid = state["slide_id"]
    analysis = state.get("analysis", {})
    cards_meta = analysis.get("cards", [])
    heros_meta = analysis.get("hero_blocks", [])
    card_htmls = state.get("card_htmls", [])
    hero_htmls = state.get("hero_htmls", [])
    content = _la._filter_content(state.get("content", {}))
    spec = state.get("design_spec", {})
    card_icons = state.get("card_icons", [])

    bg_base = state.get("bg_base_html", "")
    atmos = state.get("atmosphere_html", "")
    decor_agent_html = state.get("decoration_html", "")

    pal = spec.get("palette", {})
    accent = pal.get("accent", "#D4AF37")
    accent_soft = pal.get("accent_soft", f"{accent}55")
    frame_color = pal.get("frame_color", "rgba(212,175,55,0.35)")

    # ── 1. 배경 패턴 (aesthetic 기반)
    pattern_name = pattern_for_aesthetic(
        spec.get("aesthetic_label", ""), spec.get("decorative_motif", {})
    )
    pattern_overlay = ""
    if pattern_name:
        pattern_overlay = background_pattern(pattern_name, stroke=accent, opacity=0.18)

    # ── 2. Hub-spoke 감지 + 연결선 + Hub 강조
    layout_type = analysis.get("layout_type", "")
    is_hub_spoke = layout_type == "hub_spoke"
    connections_svg = ""
    hub_enhance = ""
    if is_hub_spoke:
        hub_center = _hub_center_from_analysis(analysis)
        if hub_center:
            card_centers = [_card_center(c) for c in cards_meta]
            connections_svg = render_connections(
                hub_center, card_centers, color=accent, stroke_width=0.4,
                opacity=0.5, glow=True,
            )
            # 허브 위에 큰 글로우 아이콘 (핵심 시각 앵커)
            hub_enhance = hub_enhancement_html(
                cx_pct=hub_center[0], cy_pct=hub_center[1],
                size_pct=16.0, accent=accent, inner_icon="network_wired",
            )

    elements = ""

    # Heroes (hub-spoke면 hub_enhance가 대신 시각 중심 역할)
    for i, html in enumerate(hero_htmls):
        if i >= len(heros_meta):
            break
        h = heros_meta[i]
        left = h.get("x1", 0) * 100; top = h.get("y1", 0) * 100
        width = (h.get("x2", 1) - h.get("x1", 0)) * 100
        height = (h.get("y2", 1) - h.get("y1", 0)) * 100
        frame_overlay = shape_html("gold_hairline_frame", stroke=frame_color, opacity=1.0)
        corner = shape_html("corner_bracket_tl", stroke=accent, opacity=0.7,
                            x_pct=0, y_pct=0, size_pct=8)
        elements += f'''<div class="hero-wrap-{i+1}" style="position:absolute;left:{left:.1f}%;top:{top:.1f}%;width:{width:.1f}%;height:{height:.1f}%;z-index:20;">
  <div style="position:absolute;inset:0;">{html}</div>
  {frame_overlay}
  {corner}
</div>
'''

    # Cards — icon 주입 + bottom accent bar
    use_bottom_bar = spec.get("frame_system", {}).get("bottom_accent_bar", False)
    for i, html in enumerate(card_htmls):
        if i >= len(cards_meta):
            break
        c = cards_meta[i]
        left = c.get("x1", 0) * 100; top = c.get("y1", 0) * 100
        width = (c.get("x2", 1) - c.get("x1", 0)) * 100
        height = (c.get("y2", 1) - c.get("y1", 0)) * 100

        icon_match = next((ic for ic in card_icons if ic["card_idx"] == i + 1), None)
        icon_html = icon_match["html_snippet"] if icon_match else ""

        if icon_html and (".card-icon" in html or 'class="card-icon"' in html):
            patched = re.sub(
                r'(<div[^>]*class="[^"]*card-icon[^"]*"[^>]*>)(.*?)(</div>)',
                lambda m: m.group(1) + icon_html + m.group(3),
                html, count=1, flags=re.DOTALL,
            )
            inner = patched
        else:
            inner = html

        bottom_bar = shape_html("bottom_accent_bar", fill=accent, opacity=1.0) if use_bottom_bar else ""

        elements += f'''<div class="card-wrap-{i+1}" style="position:absolute;left:{left:.1f}%;top:{top:.1f}%;width:{width:.1f}%;height:{height:.1f}%;z-index:10;">
  <div style="position:absolute;inset:0;">{inner}</div>
  {bottom_bar}
</div>
'''

    # Title
    title = content.get("title", "")
    desc = content.get("description", "")
    title_div = ""
    if title:
        typo = spec.get("typography", {})
        family = typo.get("hero_family", "serif")
        text_bright = pal.get("text_bright", "#F5F5F0")
        title_div = f"""<div style="position:absolute;left:50%;top:3%;transform:translateX(-50%);z-index:25;text-align:center;max-width:90%;">
    <div style="font-family:{family};font-size:1.75rem;font-weight:700;color:{accent};letter-spacing:0.08em;text-transform:uppercase;">{title}</div>
    {'<div style="font-size:0.75rem;color:' + text_bright + ';margin-top:4px;opacity:0.85;">' + desc + '</div>' if desc else ''}
</div>"""

    # Ambient geometric decorations (hub-spoke 아닐 때만 구석 장식)
    motif = spec.get("decorative_motif", {}).get("style", "minimal")
    geo_decor = ""
    if not is_hub_spoke and ("geometric" in motif or "triangle" in motif or "hexagon" in motif):
        geo_decor += shape_html("triangle_outline", stroke=accent, opacity=0.15,
                                x_pct=2, y_pct=10, size_pct=6)
        geo_decor += shape_html("hexagon_outline", stroke=accent, opacity=0.12,
                                x_pct=92, y_pct=5, size_pct=5)
        geo_decor += shape_html("circle_outline", stroke=accent, opacity=0.12,
                                x_pct=0, y_pct=80, size_pct=10)
        geo_decor += shape_html("triangle_outline", stroke=accent, opacity=0.1,
                                x_pct=80, y_pct=80, size_pct=7)

    assembled = f"""<div class="slide-container {sid}" style="width:1280px;height:720px;position:relative;overflow:hidden;font-family:'Noto Sans KR',sans-serif;">
    <div style="position:absolute;inset:0;z-index:0;">{bg_base}</div>
    <div style="position:absolute;inset:0;z-index:1;pointer-events:none;">{pattern_overlay}</div>
    <div style="position:absolute;inset:0;z-index:2;pointer-events:none;">{atmos}</div>
    <div style="position:absolute;inset:0;z-index:3;pointer-events:none;">{connections_svg}</div>
    <div style="position:absolute;inset:0;z-index:4;pointer-events:none;">{decor_agent_html}{geo_decor}</div>
    {hub_enhance}
    {elements}
    {title_div}
</div>"""
    # Post-process: 카드/히어로의 텍스트 슬롯에 걸린 display:none 제거
    assembled = _ensure_text_visible(assembled)
    return {"assembled_raw": assembled, "bg_html": bg_base}


# ════════════════════════════════════════════════════════════
# Pipeline v9 (v8 구조 동일, assembler만 v9으로)
# ════════════════════════════════════════════════════════════

def build_pipeline_v9():
    g = StateGraph(StateV5)
    g.add_node("analyzer", analyzer_v3)
    g.add_node("design_director", design_director)
    g.add_node("base_bg_agent", base_bg_agent)
    g.add_node("atmosphere_agent", atmosphere_agent)
    g.add_node("decoration_agent", decoration_agent)
    g.add_node("card_detail_agents", card_detail_agents_v5)
    g.add_node("hero_detail_agents", hero_detail_agents_v5)
    g.add_node("icon_agent", icon_agent_node)
    g.add_node("assembler", assembler_v9)  # ← v9
    g.add_node("style_normalizer", _la.style_normalizer)
    g.add_node("text_inserter", text_inserter_v3)

    g.add_edge(START, "analyzer")
    g.add_edge("analyzer", "design_director")

    g.add_edge("design_director", "base_bg_agent")
    g.add_edge("design_director", "atmosphere_agent")
    g.add_edge("design_director", "decoration_agent")
    g.add_edge("design_director", "card_detail_agents")
    g.add_edge("design_director", "hero_detail_agents")
    g.add_edge("design_director", "icon_agent")

    g.add_edge("base_bg_agent", "assembler")
    g.add_edge("atmosphere_agent", "assembler")
    g.add_edge("decoration_agent", "assembler")
    g.add_edge("card_detail_agents", "assembler")
    g.add_edge("hero_detail_agents", "assembler")
    g.add_edge("icon_agent", "assembler")

    g.add_edge("assembler", "style_normalizer")
    g.add_edge("style_normalizer", "text_inserter")
    g.add_edge("text_inserter", END)
    return g.compile()


_pipeline = None

def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline_v9()
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
