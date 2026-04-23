"""RQ1 ablation: LayerAgent WITHOUT Style Normalizer.

Stage 0 (Layout Analyzer) → Stage 1 (Background + Card Detail Agents) → [skip Stage 2] → Stage 3 (Text Inserter)
"""
from __future__ import annotations


def run(image_path: str, content_json: str, model: str = "gpt-4o") -> str:
    """Stage 2 (Style Normalizer) 건너뛴 버전.

    TODO: src/ 코드에 skip_style_normalizer 플래그 추가 후 연결.
    """
    raise NotImplementedError("Enable skip_style_normalizer=True in layeragent_full pipeline")
