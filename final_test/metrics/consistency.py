"""ConsistencyScore — RQ1 headline metric.

카드 간 CSS 속성의 변동계수(coefficient of variation) 기반 일관성 점수.
값이 높을수록 카드 간 스타일이 균일함을 의미한다.

ConsistencyScore = 1 - mean(σ_normalized(prop_i) across sibling cards within slide)

추적 속성 (6종):
- border_radius
- box_shadow_blur  (box-shadow의 첫번째 blur 값)
- box_shadow_alpha (box-shadow rgba의 alpha 채널)
- background_rgb_distance (평균 bg 색과의 거리)
- background_alpha (rgba(...) alpha)
- border_width
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from bs4 import BeautifulSoup


PROPERTIES = (
    "border_radius",
    "box_shadow_blur",
    "box_shadow_alpha",
    "background_alpha",
    "border_width",
    "background_rgb_distance",
)


@dataclass
class CardStyle:
    border_radius: float | None = None
    box_shadow_blur: float | None = None
    box_shadow_alpha: float | None = None
    background_alpha: float | None = None
    border_width: float | None = None
    background_rgb: tuple[float, float, float] | None = None


_UNIT_PX = re.compile(r"(-?\d+\.?\d*)\s*px")
_RGBA = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9.]+)\s*)?\)")


def _first_px(s: str) -> float | None:
    m = _UNIT_PX.search(s or "")
    return float(m.group(1)) if m else None


def _rgba(s: str) -> tuple[int, int, int, float] | None:
    m = _RGBA.search(s or "")
    if not m:
        return None
    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    a = float(m.group(4)) if m.group(4) else 1.0
    return r, g, b, a


def parse_card_style(style_text: str) -> CardStyle:
    """Inline style 문자열에서 일관성 관련 속성을 추출한다."""
    cs = CardStyle()
    for decl in (style_text or "").split(";"):
        if ":" not in decl:
            continue
        key, val = decl.split(":", 1)
        key, val = key.strip().lower(), val.strip()

        if key == "border-radius":
            cs.border_radius = _first_px(val)
        elif key == "box-shadow":
            cs.box_shadow_blur = _first_px(val)
            rgba = _rgba(val)
            if rgba is not None:
                cs.box_shadow_alpha = rgba[3]
        elif key in ("background", "background-color"):
            rgba = _rgba(val)
            if rgba is not None:
                r, g, b, a = rgba
                cs.background_rgb = (r, g, b)
                cs.background_alpha = a
        elif key == "border-width":
            cs.border_width = _first_px(val)
        elif key == "border":
            cs.border_width = _first_px(val) or cs.border_width
    return cs


def extract_cards(html: str, card_selector: str = ".card") -> list[CardStyle]:
    """HTML에서 카드 요소들의 스타일을 뽑는다.

    기본 selector는 `.card`. LayerAgent 출력은 div.card 형태를 가정한다.
    """
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(card_selector)
    if not cards:
        # fallback: top-level div들 중 style이 있는 것들
        cards = [d for d in soup.find_all("div") if d.get("style")]
    return [parse_card_style(c.get("style", "")) for c in cards]


def _cv(values: Iterable[float]) -> float:
    """coefficient of variation. 평균이 0이면 0 반환."""
    vs = [v for v in values if v is not None and not math.isnan(v)]
    if len(vs) < 2:
        return 0.0
    mean = sum(vs) / len(vs)
    if abs(mean) < 1e-9:
        return 0.0
    var = sum((v - mean) ** 2 for v in vs) / len(vs)
    return math.sqrt(var) / abs(mean)


def _rgb_distance_cv(rgbs: list[tuple[float, float, float] | None]) -> float:
    """카드별 bg 색의 평균 대비 평균 거리 (정규화)."""
    vs = [c for c in rgbs if c is not None]
    if len(vs) < 2:
        return 0.0
    mr = sum(v[0] for v in vs) / len(vs)
    mg = sum(v[1] for v in vs) / len(vs)
    mb = sum(v[2] for v in vs) / len(vs)
    dists = [math.sqrt((v[0] - mr) ** 2 + (v[1] - mg) ** 2 + (v[2] - mb) ** 2) for v in vs]
    mean_dist = sum(dists) / len(dists)
    max_possible = math.sqrt(3 * 255 ** 2)
    return mean_dist / max_possible


def consistency_score(html: str, card_selector: str = ".card") -> dict:
    """슬라이드 HTML의 cross-card consistency score를 계산한다.

    Returns:
        {
            "score": float in [0, 1],
            "per_property_cv": {prop: cv, ...},
            "n_cards": int,
        }
    """
    cards = extract_cards(html, card_selector)
    if len(cards) < 2:
        return {"score": 1.0, "per_property_cv": {}, "n_cards": len(cards)}

    cv_map: dict[str, float] = {}
    cv_map["border_radius"] = _cv([c.border_radius for c in cards])
    cv_map["box_shadow_blur"] = _cv([c.box_shadow_blur for c in cards])
    cv_map["box_shadow_alpha"] = _cv([c.box_shadow_alpha for c in cards])
    cv_map["background_alpha"] = _cv([c.background_alpha for c in cards])
    cv_map["border_width"] = _cv([c.border_width for c in cards])
    cv_map["background_rgb_distance"] = _rgb_distance_cv([c.background_rgb for c in cards])

    # CV는 이론적으로 unbounded이지만 실용상 1.0으로 clip
    clipped = {k: min(v, 1.0) for k, v in cv_map.items()}
    mean_cv = sum(clipped.values()) / len(clipped)
    return {
        "score": 1.0 - mean_cv,
        "per_property_cv": cv_map,
        "n_cards": len(cards),
    }


if __name__ == "__main__":
    import json
    import sys

    html = sys.stdin.read() if len(sys.argv) == 1 else open(sys.argv[1]).read()
    print(json.dumps(consistency_score(html), indent=2))
