"""Background 3-split: base / atmosphere / decoration agents."""
from __future__ import annotations

import json

from ..prompts.bg import BASE_BG_PROMPT, ATMOSPHERE_PROMPT, DECORATION_PROMPT
from ..utils.common import extract_html
from ..utils.llm import vision_call
from .design_director import spec_to_hint


def base_bg_agent(state) -> dict:
    spec = state.get("design_spec", {})
    sid = state["slide_id"]
    prompt = BASE_BG_PROMPT.format(spec_hint=spec_to_hint(spec), slide_id=sid)
    raw = vision_call(state["image_b64"], prompt, state.get("model", "gpt-4o"), max_tokens=2000)
    return {"bg_base_html": extract_html(raw)}


def atmosphere_agent(state) -> dict:
    spec = state.get("design_spec", {})
    if not spec.get("atmosphere", {}).get("has_radial_glow", False):
        return {"atmosphere_html": ""}
    sid = state["slide_id"]
    prompt = ATMOSPHERE_PROMPT.format(spec_hint=spec_to_hint(spec), slide_id=sid)
    raw = vision_call(state["image_b64"], prompt, state.get("model", "gpt-4o"), max_tokens=1500)
    return {"atmosphere_html": extract_html(raw)}


def decoration_agent(state) -> dict:
    spec = state.get("design_spec", {})
    analysis = state.get("analysis", {})
    decor_meta = analysis.get("decorations", [])
    motif = spec.get("decorative_motif", {}).get("style", "minimal")
    if motif == "minimal" and not decor_meta:
        return {"decoration_html": ""}
    sid = state["slide_id"]
    prompt = DECORATION_PROMPT.format(
        spec_hint=spec_to_hint(spec),
        slide_id=sid,
        decorations_json=json.dumps(decor_meta, ensure_ascii=False, indent=2)[:2000],
    )
    raw = vision_call(state["image_b64"], prompt, state.get("model", "gpt-4o"), max_tokens=2500)
    return {"decoration_html": extract_html(raw)}
