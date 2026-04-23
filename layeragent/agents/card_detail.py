"""Card Detail Agents — bbox-highlighted full image + CV facts + DesignSpec."""
from __future__ import annotations

from ..libraries.cv_extractors import visual_facts, format_facts_as_prompt
from ..prompts.card import CARD_DETAIL_PROMPT
from ..utils.bbox import draw_bbox_on_image
from ..utils.common import extract_html
from ..utils.llm import vision_call


def card_detail_agents(state) -> dict:
    model = state.get("model", "gpt-4o")
    full = state["image_b64"]
    analysis = state.get("analysis", {})
    spec = state.get("design_spec", {})
    cards_meta = analysis.get("cards", [])
    palette_global = analysis.get("global_palette", {})
    aesthetic = spec.get("aesthetic_label") or analysis.get("aesthetic", "")
    palette_hint = ", ".join(f"{k}={v}" for k, v in palette_global.items() if v) or "(분석 못함)"

    use_cv_facts = state.get("ablation", "none") != "no_cv_facts"

    card_htmls: list[str] = []
    card_positions: list[dict] = []
    for i, card in enumerate(cards_meta):
        bbox = (card.get("x1", 0), card.get("y1", 0), card.get("x2", 1), card.get("y2", 1))

        facts_block = ""
        if use_cv_facts:
            try:
                facts = visual_facts(full, bbox_ratio=bbox)
                facts_block = format_facts_as_prompt(facts)
            except Exception:
                pass

        highlighted = draw_bbox_on_image(full, bbox, color=(255, 0, 0), width=6, label=f"CARD_{i+1}")
        prompt = CARD_DETAIL_PROMPT.format(
            card_idx=i + 1, facts_block=facts_block,
            palette_hint=palette_hint, aesthetic_hint=aesthetic,
        )
        raw = vision_call(highlighted, prompt, model, max_tokens=6000)
        card_htmls.append(extract_html(raw))

        card_positions.append({
            "card_id": f"card_{i+1}",
            "left": round(bbox[0] * 100, 1), "top": round(bbox[1] * 100, 1),
            "width": round((bbox[2] - bbox[0]) * 100, 1),
            "height": round((bbox[3] - bbox[1]) * 100, 1),
        })
    return {"card_htmls": card_htmls, "card_positions": card_positions}
