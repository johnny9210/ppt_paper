"""Chart Specialist Agent — v10 P1.

Analyzer 가 chart 영역 bbox 를 감지한 경우, 해당 영역에 대한 inline SVG 차트 생성.
전체 슬라이드가 아닌 *chart 영역* 만 담당.

현재 v10 범위:
- content 에서 numeric 배열 찾기 (metrics, stats, values)
- 있으면 bar chart / sparkline / gauge 생성
- 없으면 패턴형 placeholder chart (무의미한 막대보다 낫게)

향후 확장: Vega-Lite spec 생성 → 렌더
"""
from __future__ import annotations

import re
from typing import Any

from ..libraries.svg_primitives import bar_chart_inline, sparkline, percentage_gauge
from ..utils.common import filter_content


CHART_KEYWORDS = (
    "추이", "성과", "매출", "revenue", "trend", "chart", "graph",
    "growth", "analytics", "statistics", "metric", "performance",
)

# 시계열/트렌드 의미를 가진 키워드 — sparkline 으로 표현. 이 enum 외의
# 차트는 막대 형태로 default. 비교 가능 단위인지 판별은 별도 알고리즘이
# 필요해 의도적으로 단순화 (paper-defensible enumeration).
_TREND_KEYWORDS = (
    "추이", "추세", "트렌드", "trend", "월별", "분기별", "연도별",
    "over time", "growth", "history", "evolution", "progression",
)


def _find_chart_regions(analysis: dict, content: dict) -> list[dict]:
    """Analyzer 결과 + content 키워드로 chart 후보 bbox 식별."""
    regions: list[dict] = []

    # 1) decorations 중 chart_area 나 chart_title 이 있으면
    for d in analysis.get("decorations", []):
        dt = (d.get("type") or "").lower()
        desc = (d.get("description") or "").lower()
        if any(k.lower() in (dt + " " + desc) for k in CHART_KEYWORDS):
            regions.append({
                "bbox": (d.get("x", 0.3), d.get("y", 0.3),
                         d.get("x", 0.3) + d.get("size", 0.4),
                         d.get("y", 0.3) + d.get("size", 0.4)),
                "label": d.get("description", "chart"),
                "type": "detected_decoration",
            })

    # 2) content 의 chart_title / chart 필드가 있으면
    chart_title = content.get("chart_title") or content.get("chart")
    if chart_title and not regions:
        # 카드 아래로 자동 배치 — 카드의 max y2 를 찾아 그 아래에 chart
        cards = analysis.get("cards", []) or []
        max_card_y2 = max((c.get("y2", 0.5) for c in cards), default=0.30)
        chart_top = max(max_card_y2 + 0.03, 0.55)
        chart_bottom = 0.95
        if chart_bottom - chart_top < 0.15:
            chart_top = chart_bottom - 0.15
        regions.append({
            "bbox": (0.08, chart_top, 0.92, chart_bottom),
            "label": chart_title,
            "type": "content_hint",
        })

    return regions


def _extract_numeric_series(content: dict) -> list[float]:
    """content dict에서 숫자 시리즈 추출 (metrics, stats, values 키 우선)."""
    for key in ("metrics", "stats", "values", "data", "series"):
        arr = content.get(key)
        if isinstance(arr, list) and arr:
            # 리스트가 dict 형태면 'value' 키 추출 시도
            if isinstance(arr[0], dict):
                vals = []
                for it in arr:
                    for vk in ("value", "val", "count", "amount", "pct"):
                        if vk in it:
                            try:
                                # 숫자만 뽑음 ("₩128억" 같은 문자열에서 128)
                                s = str(it[vk])
                                m = re.search(r"-?\d+\.?\d*", s.replace(",", ""))
                                if m:
                                    vals.append(float(m.group()))
                            except Exception:
                                pass
                            break
                if len(vals) >= 2:
                    return vals
            else:
                # primitive 숫자 리스트
                vals = []
                for v in arr:
                    try:
                        m = re.search(r"-?\d+\.?\d*", str(v).replace(",", ""))
                        if m:
                            vals.append(float(m.group()))
                    except Exception:
                        pass
                if len(vals) >= 2:
                    return vals
    return []


def chart_agent(state) -> dict:
    """Chart regions 감지 후 SVG 생성해서 state['chart_html'] 에 저장.

    Special case: when slide_type is a chart-native type (bar_chart now,
    line/waterfall/etc later), render the WHOLE slide as a chart from a
    deterministic template (chart_templates.render_chart_slide) — bypassing
    card_detail. analyzer empties cards[] for these slide_types so card
    rendering is naturally skipped.
    """
    if state.get("ablation") == "no_library":
        return {"chart_html": ""}

    from ..libraries.chart_templates import is_chart_slide_type, render_chart_slide

    slide_type = (state.get("slide_type") or "").lower()
    spec = state.get("design_spec", {})
    palette = spec.get("palette", {}) or {}
    content = filter_content(state.get("content", {}))

    # Native-chart slides: full-slide deterministic render, no card pipeline.
    if is_chart_slide_type(slide_type):
        chart_html = render_chart_slide(slide_type, content, palette)
        return {"chart_html": chart_html}

    analysis = state.get("analysis", {})
    accent = palette.get("accent", "#D4AF37")

    regions = _find_chart_regions(analysis, content)
    if not regions:
        return {"chart_html": ""}

    values = _extract_numeric_series(content)
    labels: list[str] | None = None

    # label 추출 시도
    for key in ("metrics", "stats", "values"):
        arr = content.get(key)
        if isinstance(arr, list) and arr and isinstance(arr[0], dict):
            labels = [str(it.get("title") or it.get("label") or it.get("month") or "")[:8]
                      for it in arr]
            break

    parts: list[str] = []
    for r in regions:
        x1, y1, x2, y2 = r["bbox"]
        left = x1 * 100
        top = y1 * 100
        width = (x2 - x1) * 100
        height = (y2 - y1) * 100
        px_w = int((x2 - x1) * 1280)
        px_h = int((y2 - y1) * 720)

        label_lower = (r["label"] or "").lower()
        is_trend = any(k in label_lower for k in _TREND_KEYWORDS)

        if len(values) >= 3 and not is_trend:
            svg = bar_chart_inline(values, labels=labels, color=accent,
                                    width_px=min(px_w, 600), height_px=min(px_h, 300))
        elif len(values) == 1 and not is_trend:
            svg = percentage_gauge(values[0] if values[0] <= 100 else 50,
                                    color=accent, size_px=min(px_w, px_h, 150))
        else:
            # 시계열 트렌드 패턴 (8 포인트, 우상향)
            fake = [10, 18, 16, 26, 32, 38, 48, 62]
            svg = sparkline(fake, color=accent, width_px=min(px_w - 40, 520),
                            height_px=min(px_h - 60, 140))

        parts.append(f'''<div style="position:absolute;left:{left:.1f}%;top:{top:.1f}%;
                        width:{width:.1f}%;height:{height:.1f}%;z-index:8;
                        display:flex;flex-direction:column;align-items:center;justify-content:center;
                        padding:2%;">
  <div style="font-size:0.8rem;color:rgba(255,255,255,0.7);margin-bottom:8px;font-weight:600;">{r["label"]}</div>
  {svg}
</div>''')

    return {"chart_html": "\n".join(parts)}
