"""Method B — Visual CoT.

Wraps src/methods/visual_cot.py::generate_with_content.
"""
from __future__ import annotations

from . import _common
from src.methods import visual_cot as _vcot


def run(slide_id: str, seed: int = 0, model: str = "gpt-4o") -> str:
    meta = _common.load_meta()
    design = _common.get_design_by_id(meta, slide_id)
    image_b64 = _common.b64_image(slide_id)
    client = _common.get_openai_client(seed=seed)
    _, raw = _vcot.generate_with_content(client, image_b64, design["content"], model=model)
    return _common.extract_html(raw)
