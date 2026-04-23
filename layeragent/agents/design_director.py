"""Design Director — 전체 이미지 + CV facts → DesignSpec (blackboard)."""
from __future__ import annotations

import json
import re

from ..libraries.cv_extractors import visual_facts, format_facts_as_prompt
from ..prompts.director import DIRECTOR_PROMPT
from ..utils.llm import vision_call


def _fallback_spec(facts: dict) -> dict:
    palette = facts.get("palette", [])
    bg_prim = palette[0]["hex"] if palette else "#0A1530"
    bg_sec = palette[1]["hex"] if len(palette) > 1 else "#1C2D49"
    accent = next((p["hex"] for p in palette if p.get("role_guess") == "accent"), "#D4AF37")
    return {
        "aesthetic_label": "unknown",
        "typography": {"hero_family": "sans-serif", "hero_weight": 800, "hero_style_hint": "normal",
                       "body_family": "sans-serif", "body_weight": 500, "letter_spacing_hint": "normal"},
        "palette": {"bg_primary": bg_prim, "bg_secondary": bg_sec, "accent": accent,
                    "accent_soft": accent + "55", "frame_color": "rgba(255,255,255,0.15)",
                    "text_bright": "#F5F5F0", "text_muted": "rgba(200,200,200,0.7)"},
        "frame_system": {"hero_frame": "subtle glass frame", "card_frame": "1px rgba white border",
                         "bottom_accent_bar": False},
        "decorative_motif": {"style": "minimal", "density": "sparse", "detected_shapes": []},
        "atmosphere": {"has_radial_glow": False, "glow_origin": "none",
                       "glow_color": "rgba(255,255,255,0.05)", "background_depth": "flat"},
    }


def run_director(image_b64: str, model: str = "gpt-4o") -> dict:
    facts = visual_facts(image_b64)
    facts_block = format_facts_as_prompt(facts)
    raw = vision_call(image_b64, DIRECTOR_PROMPT.replace("{facts_block}", facts_block), model, max_tokens=2000)
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return _fallback_spec(facts)
    try:
        return json.loads(m.group(0))
    except Exception:
        return _fallback_spec(facts)


def design_director(state) -> dict:
    spec = run_director(state["image_b64"], state.get("model", "gpt-4o"))
    return {"design_spec": spec}


def spec_to_hint(spec: dict) -> str:
    """DesignSpec → 프롬프트에 붙이는 요약 hint."""
    pal = spec.get("palette", {})
    typo = spec.get("typography", {})
    frame = spec.get("frame_system", {})
    motif = spec.get("decorative_motif", {})
    atmos = spec.get("atmosphere", {})
    return "\n".join([
        "**Design Director가 결정한 디자인 언어 (반드시 준수)**:",
        f"- Aesthetic: {spec.get('aesthetic_label','unknown')}",
        f"- Typography: hero={typo.get('hero_family','sans')}/w{typo.get('hero_weight',800)}/{typo.get('hero_style_hint','normal')}",
        f"- Palette: bg={pal.get('bg_primary','#000')}/accent={pal.get('accent','#888')}/frame={pal.get('frame_color','')}/text_bright={pal.get('text_bright','#fff')}",
        f"- Frame: hero={frame.get('hero_frame','')}; card={frame.get('card_frame','')}; bottom_bar={frame.get('bottom_accent_bar', False)}",
        f"- Motif: {motif.get('style','minimal')} (density {motif.get('density','sparse')})",
        f"- Atmosphere: glow={atmos.get('has_radial_glow',False)} from {atmos.get('glow_origin','none')}, depth={atmos.get('background_depth','flat')}",
    ])
