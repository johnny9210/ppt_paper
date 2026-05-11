"""Design Director — 전체 이미지 + CV facts → DesignSpec (blackboard)."""
from __future__ import annotations

import json
import re

from ..libraries.cv_extractors import visual_facts, format_facts_as_prompt
from ..prompts.director import DIRECTOR_PROMPT
from ..utils.llm import vision_call


def _fallback_spec(facts: dict) -> dict:
    palette = facts.get("palette", [])
    margin = facts.get("margin_bg") or {}
    # Prefer margin-sampled background over modal palette — see cv_extractors.
    bg_prim = margin.get("hex") or (palette[0]["hex"] if palette else "#0A1530")
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


def _hex_distance(a: str, b: str) -> float:
    """Euclidean RGB distance between two #RRGGBB strings (0..441)."""
    try:
        ar = (int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16))
        br = (int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16))
    except Exception:
        return 999.0
    return ((ar[0] - br[0]) ** 2 + (ar[1] - br[1]) ** 2 + (ar[2] - br[2]) ** 2) ** 0.5


def _enforce_margin_bg(spec: dict, margin_hex: str | None, is_uniform: bool) -> dict:
    """If margin sampling shows a uniform border color but the LLM chose a
    far-away bg_primary, override to the margin color. The margin is the most
    reliable evidence for *real* slide background (no panels can leak there).
    Also: when bg_primary becomes light, force bg_secondary to a near-white
    so the base_bg agent doesn't render a white→navy gradient.
    """
    if not margin_hex or not is_uniform:
        return spec
    pal = spec.setdefault("palette", {})
    chosen = pal.get("bg_primary", "")
    if not chosen or _hex_distance(chosen, margin_hex) > 60:
        pal["bg_primary"] = margin_hex
        try:
            r = int(margin_hex[1:3], 16); g = int(margin_hex[3:5], 16); b = int(margin_hex[5:7], 16)
            luma = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        except Exception:
            luma = 0.5
        if luma > 0.65:
            # Light slide → bg_secondary should also be light (subtle gradient,
            # not a hard white→dark bleed). Without this, base_bg renders
            # `linear-gradient(#FFFFFF, #07365C)` which dominates the slide.
            sec = pal.get("bg_secondary", "")
            if not sec or _hex_distance(sec, margin_hex) > 60:
                pal["bg_secondary"] = "#F4F6F8"
            # Flip text_bright dark for legibility on light bg.
            pal.setdefault("text_bright", "#1A2230")
            if pal.get("text_bright", "").upper() in ("#F5F5F0", "#FFFFFF", "#FFF"):
                pal["text_bright"] = "#1A2230"
    return spec


def run_director(image_b64: str, model: str = "gpt-4o") -> tuple[dict, dict]:
    """Returns (spec, facts). facts is exposed so callers can do margin-bg
    enforcement / chat-mode cross-checks without recomputing CV."""
    facts = visual_facts(image_b64)
    facts_block = format_facts_as_prompt(facts)
    raw = vision_call(image_b64, DIRECTOR_PROMPT.replace("{facts_block}", facts_block), model, max_tokens=2000)
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return _fallback_spec(facts), facts
    try:
        return json.loads(m.group(0)), facts
    except Exception:
        return _fallback_spec(facts), facts


def design_director(state) -> dict:
    spec, facts = run_director(state["image_b64"], state.get("model", "gpt-4o"))

    # Enforcement #1 — margin-sampled background overrides LLM hallucination.
    mb = facts.get("margin_bg") or {}
    spec = _enforce_margin_bg(spec, mb.get("hex"), mb.get("is_uniform", False))

    # Enforcement #2 — chat-mode cross-check. If the chat_parser also extracted
    # a background hex from the image and it agrees with the margin sample,
    # treat it as additional confirmation. If the chat-mode background is
    # close to margin and far from director's choice, prefer the chat value.
    state_style = state.get("style") or {}
    chat_bg = state_style.get("background")
    pal = spec.setdefault("palette", {})
    if chat_bg and mb.get("hex") and _hex_distance(chat_bg, mb["hex"]) < 40:
        pal["bg_primary"] = chat_bg
        chat_text = state_style.get("text_color")
        if chat_text:
            pal["text_bright"] = chat_text

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
