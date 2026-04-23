"""CCR (Content Completeness Rate) + CSS Richness.

기존 metrics/content_completeness.py와 css_effect_preservation.py의 포팅.
"""
from __future__ import annotations

import re
from typing import Iterable


_CSS_EFFECT_PROPS = (
    "box-shadow",
    "background-image",
    "linear-gradient",
    "radial-gradient",
    "conic-gradient",
    "filter",
    "backdrop-filter",
    "opacity",
    "transform",
    "border-radius",
)


def ccr(reference_texts: Iterable[str], generated_html: str) -> dict:
    """Content Completeness Rate — 입력 텍스트의 몇 %가 HTML에 나타나는가.

    문자열 매칭 기반 (관대한 buffer 포함).
    """
    items = [t.strip() for t in reference_texts if t and t.strip()]
    if not items:
        return {"ccr": 1.0, "n_items": 0, "n_found": 0}
    norm_html = re.sub(r"\s+", " ", generated_html.lower())
    found = 0
    for txt in items:
        needle = re.sub(r"\s+", " ", txt.lower())
        if needle in norm_html:
            found += 1
    return {"ccr": found / len(items), "n_items": len(items), "n_found": found}


def css_richness(html: str) -> dict:
    """CSS Richness — CSS 시각 효과 속성의 등장 횟수 총합 (proxy)."""
    # style 속성 + <style> 블록 모두 고려
    style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.DOTALL | re.IGNORECASE)
    inline_styles = re.findall(r'style\s*=\s*"([^"]*)"', html)
    haystack = " ".join(style_blocks) + " " + " ".join(inline_styles)
    haystack = haystack.lower()

    counts: dict[str, int] = {}
    for prop in _CSS_EFFECT_PROPS:
        counts[prop] = haystack.count(prop)
    total = sum(counts.values())
    return {"css_richness": total, "breakdown": counts}


def joint_pass_rate(items: list[dict], ccr_threshold: float = 0.7, css_threshold: int = 10) -> float:
    """DreamHouse-style joint pass rate: 두 조건을 동시에 만족하는 비율."""
    if not items:
        return 0.0
    passes = sum(
        1 for x in items
        if x.get("ccr", 0) >= ccr_threshold and x.get("css_richness", 0) >= css_threshold
    )
    return passes / len(items)
