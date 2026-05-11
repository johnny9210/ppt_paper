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
    """Render decorations only when there is *evidence* of them.

    Earlier behavior: if `motif != 'minimal'`, agent runs even with zero
    detected decorations and the LLM invents shapes wholesale. Observed
    failure: McKinsey process_flow has zero geometric ornaments but the
    director labeled motif "geometric-..." and the agent fabricated a row
    of stray triangles. Fix: gate on detected_shapes/decorations evidence,
    not on the motif label.
    """
    spec = state.get("design_spec", {})
    analysis = state.get("analysis", {})
    decor_meta = analysis.get("decorations", []) or []
    motif_obj = spec.get("decorative_motif", {}) or {}
    motif = motif_obj.get("style", "minimal")
    detected_shapes = motif_obj.get("detected_shapes") or []

    # Skip when *no concrete evidence* exists, regardless of motif label.
    has_evidence = bool(decor_meta) or len(detected_shapes) >= 2
    if motif == "minimal" or not has_evidence:
        return {"decoration_html": ""}

    # Also skip if the only "decorations" found are connectors/arrows that the
    # card geometry already implies — these tend to produce duplicated tiny
    # arrows that fight the card layout.
    non_connector = [d for d in decor_meta
                     if (d.get("type") or "").lower() not in ("connector", "arrow")]
    if not non_connector:
        return {"decoration_html": ""}

    sid = state["slide_id"]
    prompt = DECORATION_PROMPT.format(
        spec_hint=spec_to_hint(spec),
        slide_id=sid,
        decorations_json=json.dumps(non_connector, ensure_ascii=False, indent=2)[:2000],
    )
    raw = vision_call(state["image_b64"], prompt, state.get("model", "gpt-4o"), max_tokens=2500)
    return {"decoration_html": extract_html(raw)}
