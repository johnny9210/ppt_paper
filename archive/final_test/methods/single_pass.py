"""Method A — Baseline (single-pass GPT-4o).

Wraps src/methods/baseline.py::generate_with_content for fair comparison.
"""
from __future__ import annotations

from . import _common
from src.methods import baseline as _baseline


def run(slide_id: str, seed: int = 0, model: str = "gpt-4o") -> str:
    """단일 패스 baseline. content를 함께 제공하는 fair 버전 사용."""
    meta = _common.load_meta()
    design = _common.get_design_by_id(meta, slide_id)
    image_b64 = _common.b64_image(slide_id)
    client = _common.get_openai_client(seed=seed)
    raw = _baseline.generate_with_content(client, image_b64, design["content"], model=model)
    return _common.extract_html(raw)
