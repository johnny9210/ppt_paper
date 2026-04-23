"""Method D₂ — LayerAgent without Text Inserter (RQ2 ablation).

Custom pipeline: analyzer → (bg || cards) → assembler → style_normalizer → END
(no text_inserter — text content is NOT placed, CCR will drop)

This ablation isolates Text Inserter's effect on content fidelity.
Reuses src/methods/crop_layer_agent nodes directly.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from . import _common
from src.methods import crop_layer_agent as _la


def _build_pipeline_no_textinserter():
    g = StateGraph(_la.CropAgentState)
    g.add_node("analyzer", _la.analyzer)
    g.add_node("background_agent", _la.background_agent)
    g.add_node("card_detail_agents", _la.card_detail_agents)
    g.add_node("assembler", _la.assembler)
    g.add_node("style_normalizer", _la.style_normalizer)
    g.add_edge(START, "analyzer")
    g.add_edge("analyzer", "background_agent")
    g.add_edge("analyzer", "card_detail_agents")
    g.add_edge("background_agent", "assembler")
    g.add_edge("card_detail_agents", "assembler")
    g.add_edge("assembler", "style_normalizer")
    g.add_edge("style_normalizer", END)  # ← text_inserter 제거
    return g.compile()


_pipeline = None

def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = _build_pipeline_no_textinserter()
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
