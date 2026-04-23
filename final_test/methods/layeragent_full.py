"""LayerAgent full pipeline (wrapper around src/methods/layer_agents_langgraph.py).

4 stages: Layout Analyzer → Background + Card Detail Agents → Style Normalizer → Text Inserter.
"""
from __future__ import annotations

import sys
from pathlib import Path

# src/ 를 path에 추가
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))


def run(image_path: str, content_json: str, model: str = "gpt-4o") -> str:
    """전체 파이프라인 실행 후 최종 HTML 반환.

    TODO: src/methods/layer_agents_langgraph.py 의 main entry를 import해서 호출.
    현재는 stub — Phase B 후속 작업에서 연결.
    """
    raise NotImplementedError(
        "Connect to src/methods/layer_agents_langgraph.py in the next iteration"
    )
