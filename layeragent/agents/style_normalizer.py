"""Style Normalizer — 카드 간 CSS 속성값 통일 (RQ1의 핵심 stage)."""
from __future__ import annotations

from ..prompts.style_normalizer import NORMALIZE_PROMPT
from ..utils.common import extract_html
from ..utils.llm import text_call


def style_normalizer(state) -> dict:
    html = state.get("assembled_raw", "")
    if not html:
        return {"assembled": ""}

    # Ablation: Style Normalizer 생략 시 assembled_raw 그대로
    if state.get("ablation") == "no_style_norm":
        return {"assembled": html}

    prompt = NORMALIZE_PROMPT.format(html=html)
    raw = text_call(prompt, state.get("model", "gpt-4o"), max_tokens=16000)
    normalized = extract_html(raw)
    if not normalized or len(normalized) < 100:
        return {"assembled": html}
    return {"assembled": normalized}
