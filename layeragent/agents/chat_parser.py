"""Chat Parser — bridge from free-form user chat to structured slide spec.

One vision call, one JSON out. The parser is the only addition needed to make
the existing 4-layer pipeline accept natural-language input instead of a
pre-defined `meta.json` entry.
"""
from __future__ import annotations

import json
import re

from ..prompts.chat_parser import CHAT_PARSER_PROMPT
from ..utils.llm import vision_call


_DEFAULT_STYLE = {
    "primary_color": "#3B82F6",
    "accent_color": "#60A5FA",
    "background": "#0F172A",
    "text_color": "#F1F5F9",
}


def _fallback_spec(user_message: str) -> dict:
    title = (user_message or "").strip().splitlines()[0][:60] or "Untitled Slide"
    return {
        "slide_type": "stats_hero",
        "content": {
            "title": title,
            "hero_metric": {"value": "—", "label": "TBD"},
            "stats": [],
        },
        "style": dict(_DEFAULT_STYLE),
    }


def chat_parser(image_b64: str, user_message: str, model: str = "gpt-4o") -> dict:
    """Parse (image, user_message) into the meta.json-shaped spec.

    Returns a dict with keys: slide_type, content, style.
    Falls back to a minimal stats_hero spec if the VLM output cannot be parsed.
    """
    prompt = CHAT_PARSER_PROMPT.format(user_message=(user_message or "").strip())
    raw = vision_call(
        image_b64,
        prompt,
        model=model,
        max_tokens=2500,
        system_prompt="You parse slide briefs into strict JSON. No prose, no fences.",
    )
    m = re.search(r"\{[\s\S]*\}", raw or "")
    if not m:
        return _fallback_spec(user_message)
    try:
        spec = json.loads(m.group(0))
    except Exception:
        return _fallback_spec(user_message)

    spec.setdefault("slide_type", "stats_hero")
    spec.setdefault("content", _fallback_spec(user_message)["content"])
    style = spec.get("style") or {}
    for k, v in _DEFAULT_STYLE.items():
        style.setdefault(k, v)
    spec["style"] = style
    return spec
