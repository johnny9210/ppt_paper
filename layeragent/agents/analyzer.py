"""Layout Analyzer — 전체 이미지 분석 후 layout_type, cards, hero_blocks, decorations, palette 추출."""
from __future__ import annotations

import json
import re

from ..prompts.analyzer import ANALYZER_PROMPT
from ..utils.llm import vision_call


def _fallback_analysis() -> dict:
    return {
        "layout_type": "horizontal_row",
        "global_palette": {},
        "aesthetic": "unknown",
        "hero_blocks": [],
        "cards": [
            {"id": f"card_{i+1}", "x1": round(0.04 + i * 0.24, 3), "y1": 0.30,
             "x2": round(0.04 + i * 0.24 + 0.22, 3), "y2": 0.85}
            for i in range(4)
        ],
        "decorations": [],
        "background": {},
    }


def analyzer(state) -> dict:
    raw = vision_call(state["image_b64"], ANALYZER_PROMPT, state.get("model", "gpt-4o"), max_tokens=2500)
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {"analysis": _fallback_analysis()}
    try:
        return {"analysis": json.loads(m.group(0))}
    except Exception:
        return {"analysis": _fallback_analysis()}
