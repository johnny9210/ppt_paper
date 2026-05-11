"""Layout Analyzer — 전체 이미지 분석 후 layout_type, cards, hero_blocks, decorations, palette 추출.

Post-processing
---------------
이미지에서 감지한 카드 개수와 실제 content 항목 수가 다르면 빈 카드/누락이 발생한다.
analyzer 끝에서 slide_type별 콘텐츠 항목 수에 맞춰 cards 를 truncate/pad 한다.
"""
from __future__ import annotations

import json
import re

from ..prompts.analyzer import ANALYZER_PROMPT
from ..utils.llm import vision_call


def _fallback_analysis() -> dict:
    return {
        "layout_type": "horizontal_row",
        "global_palette": {},
        "aesthetic": "unknown",
        "hero_blocks": [],
        "cards": [
            {"id": f"card_{i+1}", "x1": round(0.04 + i * 0.24, 3), "y1": 0.30,
             "x2": round(0.04 + i * 0.24 + 0.22, 3), "y2": 0.85}
            for i in range(4)
        ],
        "decorations": [],
        "background": {},
    }


def _content_card_count(content: dict, slide_type: str) -> int | None:
    """slide_type별로 콘텐츠가 요구하는 카드 수. None = 정보 없음(잘라내지 않음)."""
    if not isinstance(content, dict):
        return None
    st = (slide_type or "").lower()
    if st == "dashboard":
        return len(content.get("metrics", []) or [])
    if st == "timeline":
        return len(content.get("items", []) or content.get("phases", []) or [])
    if st == "pyramid":
        return len(content.get("levels", []) or [])
    if st == "hub_spoke":
        return len(content.get("spokes", []) or [])
    if st in ("comparison", "before_after"):
        return 2
    if st == "feature_grid":
        return len(content.get("features", []) or [])
    if st == "roadmap":
        return len(content.get("phases", []) or [])
    if st == "layered_stack":
        return len(content.get("layers", []) or [])
    if st == "stats_hero":
        return len(content.get("stats", []) or [])
    if st == "cover":
        return 0
    if st == "table":
        return 0   # 표는 카드 사용 안 함 — table_agent 가 단독 렌더
    return None


def _grid_cards(n: int, y1: float = 0.30, y2: float = 0.85) -> list[dict]:
    """N개 카드를 가로로 균등 분포."""
    if n <= 0:
        return []
    margin = 0.04
    gap = 0.02
    width = (1 - 2 * margin - gap * (n - 1)) / n
    out = []
    for i in range(n):
        x1 = margin + i * (width + gap)
        out.append({
            "id": f"card_{i+1}",
            "x1": round(x1, 3), "y1": round(y1, 3),
            "x2": round(x1 + width, 3), "y2": round(y2, 3),
        })
    return out


def _card_y_range(slide_type: str, content: dict) -> tuple[float, float]:
    """slide_type별 카드 영역의 세로 범위 (y1, y2). chart 가 있으면 위쪽으로 압축."""
    has_chart = bool(content.get("chart_title") or content.get("chart"))
    if (slide_type or "").lower() == "dashboard" and has_chart:
        return 0.18, 0.55       # 위 18% (제목 공간) ~ 55% (이하 차트)
    if (slide_type or "").lower() == "dashboard":
        return 0.18, 0.85
    return 0.30, 0.85


def _align_cards(analysis: dict, content: dict, slide_type: str) -> dict:
    st = (slide_type or "").lower()

    # Table 모드: 카드/히어로/장식 데코레이션을 모두 비워서 표 위에 덧씌워지지 않도록.
    # Hero 가 z-index 20+ 라 표(z=9) 를 덮는 사고가 발생.
    if st == "table":
        analysis["cards"] = []
        analysis["hero_blocks"] = []
        # decorations 는 패턴/배경용으로 남겨두되, "diamond/vs/badge" 류만 제거
        analysis["decorations"] = [
            d for d in (analysis.get("decorations") or [])
            if (d.get("type") or "").lower() not in (
                "vs_badge", "diamond", "hub_circle", "spotlight", "hub", "badge"
            )
        ]
        return analysis

    n_target = _content_card_count(content, slide_type)
    if n_target is None:
        return analysis
    cards = list(analysis.get("cards", []) or [])
    if len(cards) == n_target:
        return analysis
    y1, y2 = _card_y_range(slide_type, content)
    if len(cards) > n_target:
        analysis["cards"] = cards[:n_target]
    else:
        # Image found fewer regions than content needs — fall back to grid
        analysis["cards"] = _grid_cards(n_target, y1=y1, y2=y2)
    return analysis


def _propagate_slide_level_flags(analysis: dict) -> dict:
    """Propagate slide-level `cards_have_icons` to each card's `has_icon` if
    that per-card field wasn't set. Downstream icon_agent reads per-card."""
    slide_level = analysis.get("cards_have_icons")
    if slide_level is None:
        return analysis
    for c in analysis.get("cards", []) or []:
        if "has_icon" not in c:
            c["has_icon"] = bool(slide_level)
    return analysis


def analyzer(state) -> dict:
    raw = vision_call(state["image_b64"], ANALYZER_PROMPT, state.get("model", "gpt-4o"), max_tokens=2500)
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        analysis = _fallback_analysis()
    else:
        try:
            analysis = json.loads(m.group(0))
        except Exception:
            analysis = _fallback_analysis()

    aligned = _align_cards(analysis, state.get("content", {}), state.get("slide_type", ""))
    aligned = _propagate_slide_level_flags(aligned)
    return {"analysis": aligned}
