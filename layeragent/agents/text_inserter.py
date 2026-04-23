"""Text Inserter — 완성된 HTML 구조에 content 텍스트만 삽입 (RQ2의 핵심 stage)."""
from __future__ import annotations

import json

from ..prompts.text_insert import TEXT_INSERT_PROMPT
from ..utils.common import extract_html, filter_content
from ..utils.llm import text_call


def text_inserter(state) -> dict:
    html = state.get("assembled", "")
    if not html:
        return {"assembled": html}

    # Ablation: Text Inserter 생략 — content 없이 끝
    if state.get("ablation") == "no_text_inserter":
        return {"assembled": html}

    content = filter_content(state.get("content", {}))
    content_json = json.dumps(content, ensure_ascii=False, indent=2)
    prompt = TEXT_INSERT_PROMPT.format(html=html, content_json=content_json)

    raw = text_call(prompt, state.get("model", "gpt-4o"), max_tokens=16000)
    result = extract_html(raw)
    if not result or len(result) < 100:
        return {"assembled": html}
    return {"assembled": result}
