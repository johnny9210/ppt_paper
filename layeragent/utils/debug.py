"""Per-layer debug snapshot helpers.

When `state["debug_dir"]` is set, the pipeline wrapper dumps each layer's
output into that directory as either an openable HTML preview or a JSON
sidecar. The intent is to let humans inspect *exactly* what each agent
produced so we can pinpoint which layer is degrading the final output
(layout-from-analyzer? color-from-director? text-from-card_detail?).

Each dump is a self-contained, browser-openable HTML file so visual
debugging requires only `open file://...html`.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from .bbox import draw_multiple_bboxes
from .common import wrap_slide


# Stage colors for the analyzer overlay so cards/heroes/decorations are
# visually distinguishable when overlaid on the source image.
_HERO_COLOR = (255, 80, 80)        # warm red
_CARD_COLORS = [
    (80, 180, 255),   # blue
    (80, 230, 130),   # green
    (255, 180, 80),   # orange
    (200, 130, 255),  # purple
    (255, 220, 80),   # yellow
    (130, 255, 230),  # cyan
    (255, 130, 200),  # pink
    (180, 220, 255),  # pale blue
]
_DECOR_COLOR = (200, 200, 200)


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def dump_html(debug_dir: str | Path, stage: str, html_fragment: str | None) -> Path:
    """Wrap a fragment in the standard slide shell and save."""
    p = ensure_dir(debug_dir) / f"{stage}.html"
    p.write_text(wrap_slide(html_fragment or ""))
    return p


def dump_json(debug_dir: str | Path, stage: str, obj) -> Path:
    p = ensure_dir(debug_dir) / f"{stage}.json"
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    return p


def dump_image_b64(debug_dir: str | Path, stage: str, image_b64: str) -> Path:
    p = ensure_dir(debug_dir) / f"{stage}.png"
    p.write_bytes(base64.b64decode(image_b64))
    return p


def dump_analyzer_overlay(
    debug_dir: str | Path,
    stage: str,
    image_b64: str,
    analysis: dict,
) -> Path:
    """Draw analyzer-detected hero/card/decoration bboxes on the source image.

    The output is a PNG that visually shows whether the analyzer correctly
    identified the slide's geometric layout — usually the first thing to
    check when downstream layers misbehave.
    """
    bboxes: list[dict] = []
    for h in analysis.get("hero_blocks", []) or []:
        bboxes.append({
            "bbox": (h.get("x1", 0), h.get("y1", 0), h.get("x2", 1), h.get("y2", 1)),
            "label": f"H:{h.get('id','hero')}",
            "color": _HERO_COLOR,
        })
    for i, c in enumerate(analysis.get("cards", []) or []):
        bboxes.append({
            "bbox": (c.get("x1", 0), c.get("y1", 0), c.get("x2", 1), c.get("y2", 1)),
            "label": f"C{i+1}",
            "color": _CARD_COLORS[i % len(_CARD_COLORS)],
        })
    overlay_b64 = draw_multiple_bboxes(image_b64, bboxes) if bboxes else image_b64
    return dump_image_b64(debug_dir, stage, overlay_b64)


def _positioned_html(items: list[tuple[str, dict]]) -> str:
    """Render fragments at their bbox positions on a neutral grid background.

    items: [(html_fragment, bbox_dict_with_x1_y1_x2_y2), ...]
    """
    parts: list[str] = []
    parts.append(
        "<style>.dbg-grid{background-image:"
        "linear-gradient(rgba(255,255,255,0.06) 1px,transparent 1px),"
        "linear-gradient(90deg,rgba(255,255,255,0.06) 1px,transparent 1px);"
        "background-size:40px 40px;}</style>"
    )
    parts.append('<div class="dbg-grid" style="position:absolute;inset:0;background-color:#0a0e1a;"></div>')
    for i, (frag, bbox) in enumerate(items):
        left = bbox.get("x1", 0) * 100
        top = bbox.get("y1", 0) * 100
        width = (bbox.get("x2", 1) - bbox.get("x1", 0)) * 100
        height = (bbox.get("y2", 1) - bbox.get("y1", 0)) * 100
        parts.append(
            f'<div style="position:absolute;left:{left:.1f}%;top:{top:.1f}%;'
            f'width:{width:.1f}%;height:{height:.1f}%;outline:1px dashed rgba(255,255,255,0.25);">'
            f'<div style="position:absolute;top:-18px;left:0;font:bold 10px monospace;'
            f'color:#ffd166;background:rgba(0,0,0,0.6);padding:2px 6px;border-radius:3px;">#{i+1}</div>'
            f'<div style="position:absolute;inset:0;">{frag}</div>'
            f'</div>'
        )
    return "".join(parts)


def dump_per_card(
    debug_dir: str | Path,
    stage: str,
    htmls: list[str],
    metas: list[dict],
) -> list[Path]:
    """Save each card/hero individually + a combined positioned view."""
    out: list[Path] = []
    for i, html in enumerate(htmls):
        # Single card on a 1280x720 stage at 100% scale, centered, for inspection.
        framed = (
            '<div style="position:absolute;inset:0;background:#101524;"></div>'
            '<div style="position:absolute;left:25%;top:20%;width:50%;height:60%;'
            'outline:1px dashed rgba(255,255,255,0.25);">'
            '<div style="position:absolute;inset:0;">' + html + '</div>'
            '</div>'
        )
        out.append(dump_html(debug_dir, f"{stage}_idx{i+1}_solo", framed))

    # Positioned combined view — each fragment at its actual bbox.
    if htmls and metas:
        items = list(zip(htmls, metas[: len(htmls)]))
        out.append(dump_html(debug_dir, f"{stage}_positioned", _positioned_html(items)))
    return out


# ──────────────────────────────────────────────────────────────────────
# Per-stage dumpers used by the pipeline wrapper
# ──────────────────────────────────────────────────────────────────────

def _safe(fn):
    """Swallow dumper exceptions — debugging must never break the pipeline."""
    def w(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as e:
            print(f"[debug] {fn.__name__} failed: {e}")
    return w


@_safe
def _dump_analyzer(state, out, d):
    analysis = out.get("analysis", {})
    dump_json(d, "01a_analyzer", analysis)
    dump_analyzer_overlay(d, "01b_analyzer_overlay", state["image_b64"], analysis)


@_safe
def _dump_design_director(state, out, d):
    dump_json(d, "02_design_director", out.get("design_spec", {}))


@_safe
def _dump_base_bg(state, out, d):
    dump_html(d, "03_base_bg", out.get("bg_base_html", ""))


@_safe
def _dump_atmosphere(state, out, d):
    dump_html(d, "04_atmosphere", out.get("atmosphere_html", ""))


@_safe
def _dump_decoration(state, out, d):
    dump_html(d, "05_decoration", out.get("decoration_html", ""))


@_safe
def _dump_cards(state, out, d):
    htmls = out.get("card_htmls", [])
    if not htmls:
        return
    metas = state.get("analysis", {}).get("cards", []) or []
    dump_per_card(d, "06_card", htmls, metas)


@_safe
def _dump_heros(state, out, d):
    htmls = out.get("hero_htmls", [])
    if not htmls:
        return
    metas = state.get("analysis", {}).get("hero_blocks", []) or []
    dump_per_card(d, "07_hero", htmls, metas)


@_safe
def _dump_icons(state, out, d):
    dump_json(d, "08_icons", out.get("card_icons", []))


@_safe
def _dump_chart(state, out, d):
    dump_html(d, "09_chart", out.get("chart_html", ""))


@_safe
def _dump_table(state, out, d):
    dump_html(d, "10_table", out.get("table_html", ""))


@_safe
def _dump_assembled_raw(state, out, d):
    dump_html(d, "11_assembled_raw", out.get("assembled_raw", ""))


@_safe
def _dump_normalized(state, out, d):
    dump_html(d, "12_style_normalized", out.get("assembled", ""))


@_safe
def _dump_text_inserted(state, out, d):
    dump_html(d, "13_text_inserted", out.get("assembled", ""))


@_safe
def _dump_overflow_repaired(state, out, d):
    dump_html(d, "14_overflow_repaired", out.get("assembled", ""))
    if out.get("overflow_report"):
        dump_json(d, "14_overflow_report", out["overflow_report"])


# Map node-name → dumper. The pipeline wraps nodes by name.
DUMPERS = {
    "analyzer": _dump_analyzer,
    "design_director": _dump_design_director,
    "base_bg_agent": _dump_base_bg,
    "atmosphere_agent": _dump_atmosphere,
    "decoration_agent": _dump_decoration,
    "card_detail_agents": _dump_cards,
    "hero_detail_agents": _dump_heros,
    "icon_agent": _dump_icons,
    "chart_agent": _dump_chart,
    "table_agent": _dump_table,
    "assembler": _dump_assembled_raw,
    "style_normalizer": _dump_normalized,
    "text_inserter": _dump_text_inserted,
    "overflow_repair": _dump_overflow_repaired,
}


def with_debug(node_name: str, fn):
    """Wrap a LangGraph node so its output is dumped when state['debug_dir'] is set."""
    dumper = DUMPERS.get(node_name)
    if dumper is None:
        return fn

    def wrapped(state):
        out = fn(state) or {}
        d = state.get("debug_dir")
        if d:
            dumper(state, out, d)
        return out

    wrapped.__name__ = f"debug_{node_name}"
    return wrapped
