"""Baseline A — Single-pass GPT-4o.

기존 src/methods/baseline.py 의 정제된 형태.
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
- 코드만 출력 (설명 없이)"""


def run(slide_id: str, seed: int = 0, model: str = "gpt-4o") -> str:
    meta = load_meta()
    design = get_design_by_id(meta, slide_id)
    content = filter_content(design["content"])
    content_json = json.dumps(content, ensure_ascii=False, indent=2)
    prompt = PROMPT_WITH_CONTENT.format(content_json=content_json)
    raw = vision_call(b64_image(slide_id), prompt, model, max_tokens=8000)
    return extract_html(raw)
