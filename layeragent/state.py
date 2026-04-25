"""Shared TypedDict state for LayerAgent LangGraph pipeline."""
from __future__ import annotations

from typing import TypedDict


class State(TypedDict, total=False):
    # Input
    image_b64: str
    slide_id: str
    slide_type: str
    content: dict
    style: dict
    model: str

    # Analyzer
    analysis: dict                  # {layout_type, cards, hero_blocks, decorations, global_palette, aesthetic}

    # Design Director
    design_spec: dict               # typed DesignSpec

    # BG split
    bg_base_html: str
    atmosphere_html: str
    decoration_html: str
    bg_html: str                    # back-compat alias for bg_base_html

    # Card/Hero details
    card_htmls: list[str]
    card_positions: list[dict]
    hero_htmls: list[str]
    hero_positions: list[dict]

    # Icon specialist
    card_icons: list[dict]          # [{card_idx, concept, fa_class, html_snippet, confidence}]

    # Shape detector
    detected_shapes: list[dict]

    # Chart specialist (v10 P1)
    chart_html: str

    # Table specialist (slide_type=table)
    table_html: str

    # Assembly & post-processing
    assembled_raw: str
    assembled: str
    critic_diffs: dict | None

    # Overflow repair (v10 P1)
    overflow_report: list[dict]

    # Ablation flags (set by pipeline builder)
    ablation: str                   # "none" | "no_style_norm" | "no_text_inserter" | "no_cv_facts" | "no_designspec" | "no_library" | "no_overflow_repair"
