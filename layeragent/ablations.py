"""Ablation configuration.

각 ablation 은 pipeline 실행 시 state['ablation'] 에 설정되며,
각 agent 가 조건 분기로 처리한다.

지원 ablation:
- "none"              : full pipeline (D, 논문의 main method)
- "no_style_norm"     : Style Normalizer skip (D₁ in paper)
- "no_text_inserter"  : Text Inserter skip (D₂ in paper)
- "no_cv_facts"       : CV facts (palette/OCR/HSV) prompt 주입 생략 (D₃)
- "no_designspec"     : Design Director 생략 (D₄)
- "no_library"        : Icon/Shape/Pattern library 주입 생략 (D₅)
- "no_visual_critic"  : Visual Critic stage skip (D₆)
- "crop_baseline"     : v1 스타일 crop 방식 (bbox highlight 대신 — D₇)
"""
from __future__ import annotations

SUPPORTED_ABLATIONS = (
    "none",
    "no_style_norm",
    "no_text_inserter",
    "no_cv_facts",
    "no_designspec",
    "no_library",
    "no_visual_critic",
)


def validate(ablation: str) -> str:
    if ablation not in SUPPORTED_ABLATIONS:
        raise ValueError(f"Unknown ablation '{ablation}'. Supported: {SUPPORTED_ABLATIONS}")
    return ablation
