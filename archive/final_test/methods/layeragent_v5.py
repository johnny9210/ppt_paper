"""LayerAgent v5 — Design Director + Background 3-split.

v4 대비 변경:
1. Stage 0.5 NEW: Design Director Agent (analyzer 직후) → DesignSpec 생성
2. Background Agent를 3개로 분기: Base BG / Atmosphere / Decoration
3. 모든 다운스트림 agent가 DesignSpec을 공유 (typography/palette/frame/motif/atmosphere 일관)

재사용 (v4에서): Analyzer (v3), Card/Hero Detail (v4, CV facts), Style Normalizer, Text Inserter (v3)
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from . import _common
from .bbox_utils import draw_bbox_on_image
from .cv_extractors import visual_facts, format_facts_as_prompt
from .design_director import run_design_director, spec_to_prompt_hint, DesignSpec
from .bg_agents_v5 import base_bg_agent, atmosphere_agent, decoration_agent
from .layeragent_v3 import analyzer_v3, text_inserter_v3
from .layeragent_v4 import (
    CARD_DETAIL_PROMPT_V4,
    HERO_DETAIL_PROMPT_V4,
)
from src.methods import crop_layer_agent as _la


# ════════════════════════════════════════════════════════════
# State
# ════════════════════════════════════════════════════════════

class StateV5(TypedDict, total=False):
    image_b64: str
    slide_id: str
    slide_type: str
    content: dict
    style: dict
    model: str

    analysis: dict
    card_crops_b64: list[str]
    design_spec: DesignSpec     # NEW

    bg_base_html: str           # NEW (replaces bg_html)
    atmosphere_html: str        # NEW
    decoration_html: str        # NEW
    bg_html: str                # Back-compat fallback (assembler reads from it)

    card_htmls: list[str]
    card_positions: list[dict]
    hero_htmls: list[str]
    hero_positions: list[dict]

    content_html: str
    assembled_raw: str
    assembled: str


# ════════════════════════════════════════════════════════════
# Director — Stage 0.5
# ════════════════════════════════════════════════════════════

def design_director(state: StateV5) -> dict:
    spec = run_design_director(state["image_b64"], state.get("analysis", {}), state.get("model", "gpt-4o"))
    return {"design_spec": spec}


# ════════════════════════════════════════════════════════════
# Card / Hero v5 — DesignSpec + CV facts 둘 다 주입
# ════════════════════════════════════════════════════════════

def _append_designspec(prompt: str, spec: DesignSpec) -> str:
    """CV facts 블록 + DesignSpec hint 를 프롬프트 앞에 덧붙임."""
    return spec_to_prompt_hint(spec) + "\n\n" + prompt


def card_detail_agents_v5(state: StateV5) -> dict:
    model = state.get("model", "gpt-4o")
    full = state["image_b64"]
    analysis = state.get("analysis", {})
    spec = state.get("design_spec", {})
    cards_meta = analysis.get("cards", [])

    card_htmls: list[str] = []
    card_positions: list[dict] = []
    for i, card in enumerate(cards_meta):
        bbox = (card.get("x1", 0), card.get("y1", 0), card.get("x2", 1), card.get("y2", 1))
        try:
            facts = visual_facts(full, bbox_ratio=bbox)
            facts_block = format_facts_as_prompt(facts)
        except Exception as e:
            facts_block = f"(CV 추출 실패: {e})"

        highlighted = draw_bbox_on_image(full, bbox, color=(255, 0, 0), width=6, label=f"CARD_{i+1}")
        palette_hint = ", ".join(f"{k}={v}" for k, v in analysis.get("global_palette", {}).items() if v)
        aesthetic = spec.get("aesthetic_label") or analysis.get("aesthetic", "")
        prompt_body = CARD_DETAIL_PROMPT_V4.format(
            card_idx=i + 1, facts_block=facts_block,
            palette_hint=palette_hint, aesthetic_hint=aesthetic,
        )
        prompt = _append_designspec(prompt_body, spec)
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


def hero_detail_agents_v5(state: StateV5) -> dict:
    model = state.get("model", "gpt-4o")
    full = state["image_b64"]
    analysis = state.get("analysis", {})
    spec = state.get("design_spec", {})
    heros = analysis.get("hero_blocks", [])
    if not heros:
        return {"hero_htmls": [], "hero_positions": []}

    hero_htmls: list[str] = []
    hero_positions: list[dict] = []
    for i, h in enumerate(heros):
        bbox = (h.get("x1", 0), h.get("y1", 0), h.get("x2", 1), h.get("y2", 1))
        try:
            facts = visual_facts(full, bbox_ratio=bbox)
            facts_block = format_facts_as_prompt(facts)
        except Exception as e:
            facts_block = f"(CV 추출 실패: {e})"

        highlighted = draw_bbox_on_image(full, bbox, color=(255, 0, 0), width=8, label=f"HERO_{i+1}")
        palette_hint = ", ".join(f"{k}={v}" for k, v in analysis.get("global_palette", {}).items() if v)
        aesthetic = spec.get("aesthetic_label") or analysis.get("aesthetic", "")
        prompt_body = HERO_DETAIL_PROMPT_V4.format(
            hero_idx=i + 1, facts_block=facts_block,
            palette_hint=palette_hint, aesthetic_hint=aesthetic,
        )
        prompt = _append_designspec(prompt_body, spec)
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
# Assembler v5 — 3 BG layers + hero + cards + title
# ════════════════════════════════════════════════════════════

def assembler_v5(state: StateV5) -> dict:
    sid = state["slide_id"]
    analysis = state.get("analysis", {})
    cards_meta = analysis.get("cards", [])
    heros_meta = analysis.get("hero_blocks", [])
    card_htmls = state.get("card_htmls", [])
    hero_htmls = state.get("hero_htmls", [])
    content = _la._filter_content(state.get("content", {}))

    bg_base = state.get("bg_base_html", "")
    atmos = state.get("atmosphere_html", "")
    decor = state.get("decoration_html", "")

    elements = ""

    # Heroes (z:20)
    for i, html in enumerate(hero_htmls):
        if i >= len(heros_meta):
            break
        h = heros_meta[i]
        left = h.get("x1", 0) * 100; top = h.get("y1", 0) * 100
        width = (h.get("x2", 1) - h.get("x1", 0)) * 100
        height = (h.get("y2", 1) - h.get("y1", 0)) * 100
        elements += f'<div class="hero-wrap-{i+1}" style="position:absolute;left:{left:.1f}%;top:{top:.1f}%;width:{width:.1f}%;height:{height:.1f}%;z-index:20;">\n{html}\n</div>\n'

    # Cards (z:10)
    for i, html in enumerate(card_htmls):
        if i >= len(cards_meta):
            break
        c = cards_meta[i]
        left = c.get("x1", 0) * 100; top = c.get("y1", 0) * 100
        width = (c.get("x2", 1) - c.get("x1", 0)) * 100
        height = (c.get("y2", 1) - c.get("y1", 0)) * 100
        elements += f'<div class="card-wrap-{i+1}" style="position:absolute;left:{left:.1f}%;top:{top:.1f}%;width:{width:.1f}%;height:{height:.1f}%;z-index:10;">\n{html}\n</div>\n'

    # Title
    title = content.get("title", "")
    desc = content.get("description", "")
    title_div = ""
    if title:
        spec_typo = state.get("design_spec", {}).get("typography", {})
        family = spec_typo.get("hero_family", "sans-serif")
        text_bright = state.get("design_spec", {}).get("palette", {}).get("text_bright", "#f1f5f9")
        title_div = f"""<div style="position:absolute;left:50%;top:2.5%;transform:translateX(-50%);z-index:25;text-align:center;max-width:90%;">
    <div style="font-family:{family};font-size:1.5rem;font-weight:800;color:{text_bright};text-shadow:0 2px 12px rgba(0,0,0,0.4);letter-spacing:0.02em;">{title}</div>
    {'<div style="font-size:0.7rem;color:rgba(200,200,200,0.7);margin-top:4px;">' + desc + '</div>' if desc else ''}
</div>"""

    assembled = f"""<div class="slide-container {sid}" style="width:1280px;height:720px;position:relative;overflow:hidden;font-family:'Noto Sans KR',sans-serif;">
    <div style="position:absolute;inset:0;z-index:0;">{bg_base}</div>
    <div style="position:absolute;inset:0;z-index:1;pointer-events:none;">{atmos}</div>
    <div style="position:absolute;inset:0;z-index:2;pointer-events:none;">{decor}</div>
    {elements}
    {title_div}
</div>"""
    return {"assembled_raw": assembled, "bg_html": bg_base}  # bg_html for back-compat


# ════════════════════════════════════════════════════════════
# Pipeline v5
# ════════════════════════════════════════════════════════════

def build_pipeline_v5():
    g = StateGraph(StateV5)
    g.add_node("analyzer", analyzer_v3)
    g.add_node("design_director", design_director)                  # NEW
    g.add_node("base_bg_agent", base_bg_agent)                       # NEW
    g.add_node("atmosphere_agent", atmosphere_agent)                 # NEW
    g.add_node("decoration_agent", decoration_agent)                 # NEW
    g.add_node("card_detail_agents", card_detail_agents_v5)
    g.add_node("hero_detail_agents", hero_detail_agents_v5)
    g.add_node("assembler", assembler_v5)
    g.add_node("style_normalizer", _la.style_normalizer)
    g.add_node("text_inserter", text_inserter_v3)

    g.add_edge(START, "analyzer")
    g.add_edge("analyzer", "design_director")                        # Analyzer → Director

    # Director → all renderers
    g.add_edge("design_director", "base_bg_agent")
    g.add_edge("design_director", "atmosphere_agent")
    g.add_edge("design_director", "decoration_agent")
    g.add_edge("design_director", "card_detail_agents")
    g.add_edge("design_director", "hero_detail_agents")

    # All renderers → assembler
    g.add_edge("base_bg_agent", "assembler")
    g.add_edge("atmosphere_agent", "assembler")
    g.add_edge("decoration_agent", "assembler")
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
        _pipeline = build_pipeline_v5()
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
