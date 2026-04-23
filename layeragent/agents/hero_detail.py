"""Hero Detail Agents — bbox-highlighted full image + CV facts + DesignSpec."""
from __future__ import annotations

from ..libraries.cv_extractors import visual_facts, format_facts_as_prompt
from ..prompts.hero import HERO_DETAIL_PROMPT
from ..utils.bbox import draw_bbox_on_image
from ..utils.common import extract_html
from ..utils.llm import vision_call


def hero_detail_agents(state) -> dict:
    model = state.get("model", "gpt-4o")
    full = state["image_b64"]
    analysis = state.get("analysis", {})
    spec = state.get("design_spec", {})
    heros = analysis.get("hero_blocks", [])
    if not heros:
        return {"hero_htmls": [], "hero_positions": []}

    palette_global = analysis.get("global_palette", {})
    aesthetic = spec.get("aesthetic_label") or analysis.get("aesthetic", "")
    palette_hint = ", ".join(f"{k}={v}" for k, v in palette_global.items() if v) or "(분석 못함)"
    use_cv_facts = state.get("ablation", "none") != "no_cv_facts"

    hero_htmls: list[str] = []
    hero_positions: list[dict] = []
    for i, h in enumerate(heros):
        bbox = (h.get("x1", 0), h.get("y1", 0), h.get("x2", 1), h.get("y2", 1))
        facts_block = ""
        if use_cv_facts:
            try:
                facts = visual_facts(full, bbox_ratio=bbox)
                facts_block = format_facts_as_prompt(facts)
            except Exception:
                pass

        highlighted = draw_bbox_on_image(full, bbox, color=(255, 0, 0), width=8, label=f"HERO_{i+1}")
        prompt = HERO_DETAIL_PROMPT.format(
            hero_idx=i + 1, facts_block=facts_block,
            palette_hint=palette_hint, aesthetic_hint=aesthetic,
        )
        raw = vision_call(highlighted, prompt, model, max_tokens=6000)
        hero_htmls.append(extract_html(raw))
        hero_positions.append({
            "hero_id": f"hero_{i+1}",
            "left": round(bbox[0] * 100, 1), "top": round(bbox[1] * 100, 1),
            "width": round((bbox[2] - bbox[0]) * 100, 1),
            "height": round((bbox[3] - bbox[1]) * 100, 1),
        })
    return {"hero_htmls": hero_htmls, "hero_positions": hero_positions}
