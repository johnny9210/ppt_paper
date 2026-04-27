"""Baseline A' — Single-pass GPT-4o with explicit z-index instructions.

A targeted check of Karpathy's challenge: does ONE LINE of explicit z-index
guidance close the perception-generation gap that LayerAgent's 8-stage
decomposition attacks? If yes, LayerAgent's overhead is hard to justify.

Identical to single_pass.py except for the z-index instruction block.
"""
from __future__ import annotations

import json

from layeragent.utils.common import b64_image, extract_html, filter_content, get_design_by_id, load_meta
from layeragent.utils.llm import vision_call


PROMPT_WITH_CONTENT = """이 디자인 이미지를 HTML+CSS로 변환하세요.

[삽입할 텍스트 콘텐츠]
{content_json}

규칙:
- 슬라이드 크기: 1280x720px
- 이미지의 시각적 구조를 최대한 정확히 재현
- 위 텍스트 콘텐츠를 디자인에 맞게 배치
- <style>과 <div>로 구성된 HTML 코드만 출력
- JavaScript 금지, <img> 태그 금지
- 코드만 출력 (설명 없이)

[CRITICAL — Layer hierarchy]
모든 시각 요소는 z-index를 명시적으로 지정하여 6-band 계층 구조를 따라야 한다:
- z-index: 0     — 배경 (gradient, base color)
- z-index: 2     — 분위기 (radial glow, atmosphere overlay)
- z-index: 5     — 장식 (decorative shapes, patterns, lines)
- z-index: 10    — 카드/패널 (glassmorphic cards, containers)
- z-index: 20    — 콘텐츠 (titles, body text, values)
- z-index: 30    — 아이콘/배지 (icons, badges, glow nodes)

각 요소에 position:absolute 와 명시적 z-index를 사용하여 레이어를 분리하라."""


def run(slide_id: str, seed: int = 0, model: str = "gpt-4o") -> str:
    meta = load_meta()
    design = get_design_by_id(meta, slide_id)
    content = filter_content(design["content"])
    content_json = json.dumps(content, ensure_ascii=False, indent=2)
    prompt = PROMPT_WITH_CONTENT.format(content_json=content_json)
    raw = vision_call(b64_image(slide_id), prompt, model, max_tokens=8000)
    return extract_html(raw)
