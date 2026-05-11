"""Design Director — 전체 이미지 + CV facts → DesignSpec (blackboard)."""
from __future__ import annotations

import json
import re

from ..libraries.cv_extractors import visual_facts, format_facts_as_prompt
from ..prompts.director import DIRECTOR_PROMPT
from ..utils.llm import vision_call


def _luma_hex(hex_str: str) -> float:
    try:
        r = int(hex_str[1:3], 16); g = int(hex_str[3:5], 16); b = int(hex_str[5:7], 16)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255
    except Exception:
        return 0.5


def _fallback_spec(facts: dict) -> dict:
    """Build a minimal spec entirely from image-derived facts. No magic hex —
    if facts cannot supply a color, leave the field empty so downstream agents
    fail loud rather than render against an arbitrary baseline.
    """
    palette = facts.get("palette", [])
    margin = facts.get("margin_bg") or {}
    text_colors = facts.get("text_colors") or {}

    bg_prim = margin.get("hex") or (palette[0]["hex"] if palette else "")
    bg_luma = _luma_hex(bg_prim) if bg_prim else 0.5

    # Pick a same-tone secondary from palette
    bg_sec = ""
    if palette:
        same_tone = [p for p in palette if abs(_luma_hex(p["hex"]) - bg_luma) < 0.25 and p["hex"] != bg_prim]
        if same_tone:
            bg_sec = same_tone[0]["hex"]
        elif len(palette) > 1:
            bg_sec = palette[1]["hex"]

    accent = next((p["hex"] for p in palette if p.get("role_guess") == "accent"),
                  palette[0]["hex"] if palette else "")

    # Image-derived text color: pick the ink color contrasting bg_primary.
    if bg_luma > 0.5:
        text_bright = text_colors.get("text_dark_hex") or ""
    else:
        text_bright = text_colors.get("text_light_hex") or ""
    if not text_bright and palette:
        if bg_luma > 0.5:
            text_bright = min(palette, key=lambda p: _luma_hex(p["hex"]))["hex"]
        else:
            text_bright = max(palette, key=lambda p: _luma_hex(p["hex"]))["hex"]

    return {
        "aesthetic_label": "unknown",
        "typography": {"hero_family": "sans-serif", "hero_weight": 800, "hero_style_hint": "normal",
                       "body_family": "sans-serif", "body_weight": 500, "letter_spacing_hint": "normal"},
        "palette": {"bg_primary": bg_prim, "bg_secondary": bg_sec, "accent": accent,
                    "accent_soft": (accent + "55") if accent else "",
                    "frame_color": "rgba(255,255,255,0.15)",
                    "text_bright": text_bright, "text_muted": "rgba(200,200,200,0.7)"},
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


def _enforce_margin_bg(spec: dict, facts: dict) -> dict:
    """If margin sampling shows a uniform border color but the LLM chose a
    far-away bg_primary, override to the margin color. The margin is the most
    reliable evidence for *real* slide background (no panels can leak there).

    All auxiliary colors (bg_secondary, text_bright) are also derived from the
    image — k-means palette (for same-tone bg_secondary) and OCR-bbox ink
    measurement (for contrasting text_bright). No hardcoded hex anywhere.
    """
    margin = facts.get("margin_bg") or {}
    margin_hex = margin.get("hex")
    is_uniform = bool(margin.get("is_uniform"))
    if not margin_hex or not is_uniform:
        return spec

    pal = spec.setdefault("palette", {})
    chosen = pal.get("bg_primary", "")
    if chosen and _hex_distance(chosen, margin_hex) <= 60:
        return spec

    pal["bg_primary"] = margin_hex
    bg_luma = _luma_hex(margin_hex)

    palette_facts = facts.get("palette", []) or []
    # bg_secondary: a palette color in the same luma half as bg_primary.
    sec = pal.get("bg_secondary", "")
    sec_drift = _hex_distance(sec, margin_hex) > 60 if sec else True
    sec_wrong_tone = sec and ((bg_luma > 0.5) != (_luma_hex(sec) > 0.5))
    if (not sec) or sec_drift or sec_wrong_tone:
        same_tone = [p for p in palette_facts
                     if p.get("hex") and p["hex"].upper() != margin_hex.upper()
                     and abs(_luma_hex(p["hex"]) - bg_luma) < 0.25]
        if same_tone:
            # Pick the most distinct from bg (max hex distance among same-tone)
            same_tone.sort(key=lambda p: -_hex_distance(p["hex"], margin_hex))
            pal["bg_secondary"] = same_tone[0]["hex"]

    # text_bright: image-derived ink color contrasting bg_primary.
    tc = facts.get("text_colors") or {}
    if bg_luma > 0.5:
        measured = tc.get("text_dark_hex")
    else:
        measured = tc.get("text_light_hex")
    if measured:
        cur = pal.get("text_bright", "")
        # Override if current text_bright would be illegible on the new bg.
        cur_luma = _luma_hex(cur) if cur else (1.0 - bg_luma)
        if not cur or abs(cur_luma - bg_luma) < 0.3:
            pal["text_bright"] = measured

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

    # Enforcement #1 — margin-sampled bg + image-derived auxiliary colors
    # override LLM hallucination.
    spec = _enforce_margin_bg(spec, facts)

    # Enforcement #2 — chat-mode cross-check. If the chat_parser also extracted
    # a background hex from the image and it agrees with the margin sample,
    # treat it as additional confirmation. If the chat-mode background is
    # close to margin and far from director's choice, prefer the chat value.
    mb = facts.get("margin_bg") or {}
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
