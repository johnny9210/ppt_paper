"""Icon Specialist — 카드 아이콘 개념 식별 후 FontAwesome class 매핑."""
from __future__ import annotations

import json
import re

from ..libraries.icon_library import concept_to_fa_class, fa_icon_html
from ..prompts.icon import ICON_CONCEPT_PROMPT
from ..utils.bbox import draw_bbox_on_image
from ..utils.llm import vision_call


def identify_icon_concept(image_b64: str, card_bbox, card_idx: int, model: str = "gpt-4o") -> dict:
    highlighted = draw_bbox_on_image(image_b64, card_bbox, color=(255, 0, 0), width=6,
                                      label=f"CARD_{card_idx}")
    raw = vision_call(highlighted, ICON_CONCEPT_PROMPT.format(card_idx=card_idx), model, max_tokens=500)
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {"concept": "circle", "confidence": 0.0, "rationale": "parse_fail"}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"concept": "circle", "confidence": 0.0, "rationale": "json_fail"}


def icon_agent(state) -> dict:
    # 라이브러리 생략 ablation
    if state.get("ablation") == "no_library":
        return {"card_icons": []}

    analysis = state.get("analysis", {})
    cards = analysis.get("cards", [])
    if not cards:
        return {"card_icons": []}

    spec = state.get("design_spec", {})
    accent = spec.get("palette", {}).get("accent", "#D4AF37")
    full = state["image_b64"]
    model = state.get("model", "gpt-4o")

    card_icons: list[dict] = []
    for i, card in enumerate(cards):
        bbox = (card.get("x1", 0), card.get("y1", 0), card.get("x2", 1), card.get("y2", 1))
        res = identify_icon_concept(full, bbox, i + 1, model=model)
        concept = res.get("concept", "circle")
        card_icons.append({
            "card_idx": i + 1,
            "concept": concept,
            "fa_class": concept_to_fa_class(concept),
            "html_snippet": fa_icon_html(concept, size_rem=1.8, color=accent),
            "confidence": res.get("confidence", 0.5),
        })
    return {"card_icons": card_icons}
