"""Assembler — 모든 layer 조립 + library injection (icon/shape/pattern/connections).

핵심 로직:
1. Hub-spoke 감지 시 bezier 연결선 + hub 강조 자동 주입
2. 배경 패턴 (circuit/topographic/dot/hex) aesthetic 기반 선택
3. Icon Agent의 FA HTML을 .card-icon 슬롯에 regex 주입
4. Card/Hero 주변에 shape library의 hairline frame, corner bracket, bottom accent bar 주입
5. Post-process: display:none bug 자동 복구
"""
from __future__ import annotations

import re

from ..libraries.icon_library import shape_html
from ..libraries.pattern_library import (
    render_connections,
    background_pattern,
    pattern_for_aesthetic,
    hub_enhancement_html,
)
from ..utils.common import filter_content


def _card_center(card: dict) -> tuple[float, float]:
    x = (card.get("x1", 0) + card.get("x2", 1)) / 2 * 100
    y = (card.get("y1", 0) + card.get("y2", 1)) / 2 * 100
    return (x, y)


def _hub_center_from_analysis(analysis: dict) -> tuple[float, float] | None:
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


def _ensure_text_visible(html: str) -> str:
    """card-value/card-label/hero-value 에 display:none 이 걸려있으면 제거."""
    html = re.sub(
        r'(\.card-(?:value|label|icon)\s*\{[^}]*?)display\s*:\s*none\s*;?',
        r'\1', html, flags=re.IGNORECASE,
    )
    html = re.sub(
        r'(\.hero-(?:value|subtitle)\s*\{[^}]*?)display\s*:\s*none\s*;?',
        r'\1', html, flags=re.IGNORECASE,
    )
    return html


def assembler(state) -> dict:
    sid = state["slide_id"]
    analysis = state.get("analysis", {})
    cards_meta = analysis.get("cards", [])
    heros_meta = analysis.get("hero_blocks", [])
    card_htmls = state.get("card_htmls", [])
    hero_htmls = state.get("hero_htmls", [])
    content = filter_content(state.get("content", {}))
    spec = state.get("design_spec", {})
    card_icons = state.get("card_icons", [])
    ablation = state.get("ablation", "none")
    use_library = ablation != "no_library"

    bg_base = state.get("bg_base_html", "")
    atmos = state.get("atmosphere_html", "")
    decor_agent_html = state.get("decoration_html", "")

    pal = spec.get("palette", {})
    accent = pal.get("accent", "#D4AF37")
    frame_color = pal.get("frame_color", "rgba(212,175,55,0.35)")

    # ── 1. 배경 패턴 (aesthetic 기반)
    pattern_overlay = ""
    if use_library:
        pattern_name = pattern_for_aesthetic(spec.get("aesthetic_label", ""), spec.get("decorative_motif", {}))
        if pattern_name:
            pattern_overlay = background_pattern(pattern_name, stroke=accent, opacity=0.18)

    # ── 2. Hub-spoke 감지 + 연결선 + hub 강조
    layout_type = analysis.get("layout_type", "")
    is_hub_spoke = layout_type == "hub_spoke"
    connections_svg = ""
    hub_enhance = ""
    if is_hub_spoke and use_library:
        hub_center = _hub_center_from_analysis(analysis)
        if hub_center:
            card_centers = [_card_center(c) for c in cards_meta]
            connections_svg = render_connections(
                hub_center, card_centers, color=accent, stroke_width=0.4, opacity=0.5, glow=True,
            )
            hub_enhance = hub_enhancement_html(
                cx_pct=hub_center[0], cy_pct=hub_center[1],
                size_pct=16.0, accent=accent, inner_icon="network_wired",
            )

    elements = ""

    # Heroes
    for i, html in enumerate(hero_htmls):
        if i >= len(heros_meta):
            break
        h = heros_meta[i]
        left = h.get("x1", 0) * 100; top = h.get("y1", 0) * 100
        width = (h.get("x2", 1) - h.get("x1", 0)) * 100
        height = (h.get("y2", 1) - h.get("y1", 0)) * 100
        overlays = ""
        if use_library:
            overlays = shape_html("gold_hairline_frame", stroke=frame_color, opacity=1.0)
            overlays += shape_html("corner_bracket_tl", stroke=accent, opacity=0.7,
                                    x_pct=0, y_pct=0, size_pct=8)
        elements += f'''<div class="hero-wrap-{i+1}" style="position:absolute;left:{left:.1f}%;top:{top:.1f}%;width:{width:.1f}%;height:{height:.1f}%;z-index:20;">
  <div style="position:absolute;inset:0;">{html}</div>
  {overlays}
</div>
'''

    # Cards — icon 주입 + bottom accent bar
    use_bottom_bar = spec.get("frame_system", {}).get("bottom_accent_bar", False) and use_library
    for i, html in enumerate(card_htmls):
        if i >= len(cards_meta):
            break
        c = cards_meta[i]
        left = c.get("x1", 0) * 100; top = c.get("y1", 0) * 100
        width = (c.get("x2", 1) - c.get("x1", 0)) * 100
        height = (c.get("y2", 1) - c.get("y1", 0)) * 100

        icon_match = next((ic for ic in card_icons if ic["card_idx"] == i + 1), None)
        icon_html = icon_match["html_snippet"] if icon_match else ""
        if icon_html and ("card-icon" in html):
            inner = re.sub(
                r'(<div[^>]*class="[^"]*card-icon[^"]*"[^>]*>)(.*?)(</div>)',
                lambda m: m.group(1) + icon_html + m.group(3),
                html, count=1, flags=re.DOTALL,
            )
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

    # Ambient geometric decorations (hub-spoke 아닐 때만)
    motif = spec.get("decorative_motif", {}).get("style", "minimal")
    geo_decor = ""
    if use_library and not is_hub_spoke and any(k in motif for k in ("geometric", "triangle", "hexagon")):
        geo_decor += shape_html("triangle_outline", stroke=accent, opacity=0.15, x_pct=2, y_pct=10, size_pct=6)
        geo_decor += shape_html("hexagon_outline", stroke=accent, opacity=0.12, x_pct=92, y_pct=5, size_pct=5)
        geo_decor += shape_html("circle_outline", stroke=accent, opacity=0.12, x_pct=0, y_pct=80, size_pct=10)
        geo_decor += shape_html("triangle_outline", stroke=accent, opacity=0.1, x_pct=80, y_pct=80, size_pct=7)

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
    assembled = _ensure_text_visible(assembled)
    return {"assembled_raw": assembled, "bg_html": bg_base}
