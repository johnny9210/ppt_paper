"""Method D₁ — LayerAgent without Style Normalizer (RQ1 ablation).

Custom pipeline: analyzer → (bg || cards) → assembler → [skip style_normalizer] → text_inserter
Reuses src/methods/crop_layer_agent nodes directly.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from . import _common
from src.methods import crop_layer_agent as _la


def _passthrough(state):
    """Style Normalizer 자리에 들어가서 assembled_raw → assembled로 복사만 한다."""
    return {"assembled": state.get("assembled_raw", "")}


def _build_pipeline_no_stylenorm():
    g = StateGraph(_la.CropAgentState)
    g.add_node("analyzer", _la.analyzer)
    g.add_node("background_agent", _la.background_agent)
    g.add_node("card_detail_agents", _la.card_detail_agents)
    g.add_node("assembler", _la.assembler)
    g.add_node("style_passthrough", _passthrough)  # ← style_normalizer 대체
    g.add_node("text_inserter", _la.text_inserter)
    g.add_edge(START, "analyzer")
    g.add_edge("analyzer", "background_agent")
    g.add_edge("analyzer", "card_detail_agents")
    g.add_edge("background_agent", "assembler")
    g.add_edge("card_detail_agents", "assembler")
    g.add_edge("assembler", "style_passthrough")
    g.add_edge("style_passthrough", "text_inserter")
    g.add_edge("text_inserter", END)
    return g.compile()


_pipeline = None

def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = _build_pipeline_no_stylenorm()
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
