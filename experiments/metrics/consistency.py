"""ConsistencyScore — RQ1 headline metric (v2: <style> block aware).

카드 간 시각 일관성을 측정한다. 두 가지 전략을 결합:

1. **Per-card-N 그룹 분석** (LayerAgent 류 — 카드별 클래스 사용):
   - <style>에서 `.card-1, .card-2, ...`, `.feature-1, ...`, `.step-1, ...` 형태의
     selector 그룹을 찾는다
   - 각 그룹 멤버의 6 CSS 속성을 비교해 변동계수(CV) 계산
2. **공유 클래스 분석** (Baseline 류 — `.item` 같은 단일 클래스 사용):
   - 모든 카드가 동일 클래스 → CV = 0 (자명하게 일관)
   - 단, `n_card_classes = 1` 로 보고하여 "decomposition으로 인한 inconsistency 위험이
     처음부터 발생하지 않은 케이스"임을 표시

ConsistencyScore = 1 - mean_normalized_CV
"""
from __future__ import annotations

import math
import re
from collections import defaultdict


PROPERTIES = (
    "border_radius",
    "box_shadow_blur",
    "box_shadow_alpha",
    "background_alpha",
    "border_width",
    "background_rgb_distance",
)

# 카드/요소를 나타낼 가능성이 높은 클래스 prefix
CARD_PREFIXES = ("card", "feature", "metric", "step", "item", "phase", "node", "tile", "stat", "layer", "spoke")

_RX_RULE = re.compile(r"([^{}]+)\{([^{}]+)\}", re.MULTILINE)
_RX_PX = re.compile(r"(-?\d+\.?\d*)\s*(?:px)?")
_RX_RGBA = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9.]+)\s*)?\)")


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _parse_style_blocks(html: str) -> dict[str, dict[str, str]]:
    """`<style>` 블록을 모두 모아 selector별 declaration dict로 반환."""
    blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.DOTALL | re.IGNORECASE)
    css_text = _strip_comments("\n".join(blocks))
    selector_decls: dict[str, dict[str, str]] = defaultdict(dict)
    for m in _RX_RULE.finditer(css_text):
        sel_str, body = m.group(1).strip(), m.group(2).strip()
        decls: dict[str, str] = {}
        for d in body.split(";"):
            if ":" not in d:
                continue
            k, v = d.split(":", 1)
            decls[k.strip().lower()] = v.strip()
        for sel in sel_str.split(","):
            sel = sel.strip()
            if sel.startswith("."):
                cname = sel.split(":")[0].split(">")[0].strip().lstrip(".").split(" ")[0]
                if cname:
                    selector_decls[cname].update(decls)
    return dict(selector_decls)


def _normalize_class_to_group(cls: str) -> str | None:
    """`.card-1` → `card`, `.card-2` → `card`, `.feature-3` → `feature`, `.item` → `item`."""
    cls_lower = cls.lower()
    for prefix in CARD_PREFIXES:
        # exact match (e.g., "card", "item")
        if cls_lower == prefix:
            return prefix
        # prefix-N or prefix_N or prefixN
        m = re.match(rf"^{prefix}[-_]?(\d+)$", cls_lower)
        if m:
            return prefix
    return None


def _first_px(s: str | None) -> float | None:
    if not s:
        return None
    m = _RX_PX.search(s)
    return float(m.group(1)) if m else None


def _rgba(s: str | None) -> tuple[int, int, int, float] | None:
    if not s:
        return None
    m = _RX_RGBA.search(s)
    if not m:
        return None
    a = float(m.group(4)) if m.group(4) else 1.0
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), a


def _extract_props(decls: dict[str, str]) -> dict[str, float | tuple | None]:
    """주요 속성 추출."""
    out: dict[str, float | tuple | None] = {}
    out["border_radius"] = _first_px(decls.get("border-radius"))
    bs = decls.get("box-shadow")
    out["box_shadow_blur"] = _first_px(bs)
    rgba_bs = _rgba(bs)
    out["box_shadow_alpha"] = rgba_bs[3] if rgba_bs else None
    bg = decls.get("background") or decls.get("background-color")
    rgba_bg = _rgba(bg)
    out["background_rgb"] = (rgba_bg[0], rgba_bg[1], rgba_bg[2]) if rgba_bg else None
    out["background_alpha"] = rgba_bg[3] if rgba_bg else None
    bw = decls.get("border-width") or decls.get("border")
    out["border_width"] = _first_px(bw)
    return out


def _cv(values: list[float | None]) -> float:
    vs = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if len(vs) < 2:
        return 0.0
    mean = sum(vs) / len(vs)
    if abs(mean) < 1e-9:
        return 0.0
    var = sum((v - mean) ** 2 for v in vs) / len(vs)
    return math.sqrt(var) / abs(mean)


def _rgb_dist_cv(rgbs: list[tuple[int, int, int] | None]) -> float:
    vs = [c for c in rgbs if c is not None]
    if len(vs) < 2:
        return 0.0
    mr = sum(v[0] for v in vs) / len(vs)
    mg = sum(v[1] for v in vs) / len(vs)
    mb = sum(v[2] for v in vs) / len(vs)
    dists = [math.sqrt((v[0] - mr) ** 2 + (v[1] - mg) ** 2 + (v[2] - mb) ** 2) for v in vs]
    md = sum(dists) / len(dists)
    return md / math.sqrt(3 * 255 ** 2)


def consistency_score(html: str) -> dict:
    """
    Returns:
        {
            "score": float in [0, 1] (higher = more consistent),
            "n_cards": int (cards detected in the largest group),
            "card_class_group": str | None,
            "per_property_cv": dict[str, float],
            "n_card_classes": int (number of distinct card classes; 1 = shared class),
        }
    """
    sel_decls = _parse_style_blocks(html)
    if not sel_decls:
        return {"score": 1.0, "n_cards": 0, "card_class_group": None,
                "per_property_cv": {}, "n_card_classes": 0}

    # 클래스를 그룹별로 묶음
    groups: dict[str, list[str]] = defaultdict(list)
    for cls in sel_decls:
        g = _normalize_class_to_group(cls)
        if g:
            groups[g].append(cls)

    if not groups:
        return {"score": 1.0, "n_cards": 0, "card_class_group": None,
                "per_property_cv": {}, "n_card_classes": 0}

    # 멤버가 가장 많은 그룹 (실질적 카드 그룹) 선택
    best_group = max(groups.items(), key=lambda x: len(x[1]))
    group_name, members = best_group

    if len(members) < 2:
        # 단일 클래스 — 자명하게 일관, but flag it
        return {"score": 1.0, "n_cards": 1, "card_class_group": group_name,
                "per_property_cv": {}, "n_card_classes": 1}

    # 각 멤버에서 속성 추출
    cards = [_extract_props(sel_decls[c]) for c in members]

    cv_map: dict[str, float] = {}
    cv_map["border_radius"] = _cv([c["border_radius"] for c in cards])
    cv_map["box_shadow_blur"] = _cv([c["box_shadow_blur"] for c in cards])
    cv_map["box_shadow_alpha"] = _cv([c["box_shadow_alpha"] for c in cards])
    cv_map["background_alpha"] = _cv([c["background_alpha"] for c in cards])
    cv_map["border_width"] = _cv([c["border_width"] for c in cards])
    cv_map["background_rgb_distance"] = _rgb_dist_cv([c["background_rgb"] for c in cards])

    clipped = {k: min(v, 1.0) for k, v in cv_map.items()}
    mean_cv = sum(clipped.values()) / len(clipped)
    return {
        "score": round(1.0 - mean_cv, 4),
        "n_cards": len(members),
        "card_class_group": group_name,
        "per_property_cv": {k: round(v, 4) for k, v in cv_map.items()},
        "n_card_classes": len(members),
    }


if __name__ == "__main__":
    import json
    import sys

    html = sys.stdin.read() if len(sys.argv) == 1 else open(sys.argv[1]).read()
    print(json.dumps(consistency_score(html), indent=2, ensure_ascii=False))
