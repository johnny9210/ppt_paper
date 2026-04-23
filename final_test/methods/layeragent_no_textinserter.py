"""RQ2 ablation: LayerAgent WITHOUT Text Inserter.

텍스트를 Card Detail Agent 단계에서 같이 처리 (content-style 동시 처리로 인한 트레이드오프 재현).
"""
from __future__ import annotations


def run(image_path: str, content_json: str, model: str = "gpt-4o") -> str:
    """Stage 3 (Text Inserter) 건너뛰고 Card Detail Agent가 텍스트까지 처리하는 버전.

    TODO: Card Detail Agent 프롬프트에 content_json 주입, Stage 3 skip.
    """
    raise NotImplementedError("Inject content into Card Detail Agent prompts, skip Text Inserter")
