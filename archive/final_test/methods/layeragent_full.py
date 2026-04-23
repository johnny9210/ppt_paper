"""Method D — LayerAgent (full 4-stage pipeline).

Wraps src/methods/crop_layer_agent.py::generate_from_saved_image.
Uses the LangGraph pipeline: analyzer → (background_agent || card_detail_agents)
→ assembler → style_normalizer → text_inserter → END
"""
from __future__ import annotations

from . import _common
from src.methods import crop_layer_agent as _layeragent


def run(slide_id: str, seed: int = 0, model: str = "gpt-4o") -> str:
    meta = _common.load_meta()
    design = _common.get_design_by_id(meta, slide_id)
    img_path = _common.get_image_path(slide_id)
    result = _layeragent.generate_from_saved_image(
        image_path=str(img_path),
        slide_id=slide_id,
        slide_type=design["type"],
        content=design["content"],
        style=meta["style"],
        model=model,
    )
    return _common.extract_html(result.get("assembled", ""))
