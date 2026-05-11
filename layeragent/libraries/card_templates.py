"""Deterministic card template renderer.

When DesignSpec contains a `card_template` block AND analyzer reports a uniform
grid layout (process_flow, roadmap, timeline, feature_grid, dashboard with
identical metric cards), we render every card from the same parametric
template instead of running 5 separate vision calls. This:

  - eliminates style drift across cards (the failure that style_normalizer
    was patching with a brittle most-common heuristic)
  - cuts ~5 vision calls per slide (token cost)
  - guarantees identical clip-path / bullet count / header band / footer
    band across all instances, which is the visual property that defines
    McKinsey-style chevron flows

The template is a plain dict; the renderer emits one `<style>` block plus
one `<div class="card-N">…</div>` block per index. Slots (.card-icon,
.card-value, .card-label, .card-footer) stay empty for text_inserter to
fill — same contract as the LLM-emitted cards.
"""
from __future__ import annotations


_SHAPE_CLIP = {
    "chevron":      "polygon(0 0, 90% 0, 100% 50%, 90% 100%, 0 100%, 10% 50%)",
    "chevron_lead": "polygon(0 0, 90% 0, 100% 50%, 90% 100%, 0 100%)",         # first card
    "chevron_tail": "polygon(0 0, 100% 0, 100% 100%, 0 100%, 10% 50%)",        # last card
    "pill":         None,        # use border-radius
    "hex":          "polygon(25% 0, 75% 0, 100% 50%, 75% 100%, 25% 100%, 0 50%)",
    "rect":         None,
}


def _norm_template(t: dict) -> dict:
    """Fill in defaults so partial templates still render."""
    if not t:
        return {"enabled": False}
    if not t.get("enabled"):
        return t
    out = {
        "enabled": True,
        "shape": (t.get("shape") or "rect").lower(),
        "header": {
            "bg": (t.get("header") or {}).get("bg", "#1F3864"),
            "text": (t.get("header") or {}).get("text", "#FFFFFF"),
            "padding": (t.get("header") or {}).get("padding", "0.5rem 1rem"),
            "weight": int((t.get("header") or {}).get("weight", 700)),
            "size_rem": float((t.get("header") or {}).get("size_rem", 1.0)),
            "height_pct": float((t.get("header") or {}).get("height_pct", 18)),
        },
        "body": {
            "bg": (t.get("body") or {}).get("bg", "#FFFFFF"),
            "text": (t.get("body") or {}).get("text", "#222222"),
            "padding": (t.get("body") or {}).get("padding", "0.75rem 1rem"),
            "size_rem": float((t.get("body") or {}).get("size_rem", 0.78)),
            "line_height": float((t.get("body") or {}).get("line_height", 1.35)),
        },
        "footer": {
            "enabled": bool((t.get("footer") or {}).get("enabled", False)),
            "bg": (t.get("footer") or {}).get("bg", "#FFFFFF"),
            "text": (t.get("footer") or {}).get("text", "#1F3864"),
            "content_kind": (t.get("footer") or {}).get("content_kind", "none"),
            "weight": int((t.get("footer") or {}).get("weight", 700)),
            "size_rem": float((t.get("footer") or {}).get("size_rem", 0.78)),
            "border_top": (t.get("footer") or {}).get("border_top", "1px solid rgba(0,0,0,0.12)"),
            "height_pct": float((t.get("footer") or {}).get("height_pct", 14)),
        },
        "bullets_count": max(1, int(t.get("bullets_count", 3))),
        "border_radius": t.get("border_radius", "0px"),
        "border": t.get("border", "none"),
        "card_bg": t.get("card_bg", (t.get("body") or {}).get("bg", "#FFFFFF")),
    }
    return out


def _shape_for_position(shape: str, idx: int, total: int) -> str:
    """Choose first/middle/last shape variant for chevron flows."""
    if shape != "chevron" or total <= 1:
        return shape
    if idx == 0:
        return "chevron_lead"
    if idx == total - 1:
        return "chevron_tail"
    return "chevron"


def render_card(idx_one: int, total: int, template: dict, has_icon: bool = False) -> str:
    """Render one card from template, with semantic slots empty.

    Slot contract (matches LLM-emitted cards consumed by text_inserter):
      .card-icon   — optional glyph (only present if has_icon)
      .card-value  — title / step name
      .card-label  — bullet (one div per bullet, count from template)
      .card-footer — quarter/date footer (only if template.footer.enabled)
    """
    t = _norm_template(template)
    if not t.get("enabled"):
        return ""

    shape = _shape_for_position(t["shape"], idx_one - 1, total)
    clip = _SHAPE_CLIP.get(shape)
    radius = t["border_radius"] if not clip else "0"

    h = t["header"]; b = t["body"]; f = t["footer"]

    # Chevron clip-path bites/points 10% horizontally on shaped sides — bump
    # body padding on those sides so bullet text doesn't clip into the cut.
    pad_extra_left = "1.4rem" if shape in ("chevron", "chevron_tail") else b["padding"].split()[1] if " " in b["padding"] else "0.9rem"
    pad_extra_right = "1.6rem" if shape in ("chevron", "chevron_lead") else b["padding"].split()[1] if " " in b["padding"] else "0.9rem"
    body_padding_chevron = f"0.6rem {pad_extra_right} 0.6rem {pad_extra_left}"
    body_padding = body_padding_chevron if shape.startswith("chevron") else b["padding"]
    header_padding_chevron = f"0.5rem {pad_extra_right} 0.5rem {pad_extra_left}"
    header_padding = header_padding_chevron if shape.startswith("chevron") else h["padding"]
    footer_padding = f"0.4rem {pad_extra_right} 0.4rem {pad_extra_left}" if shape.startswith("chevron") else "0.4rem 1rem"

    icon_html = '<div class="card-icon"></div>' if has_icon else ''
    bullet_divs = "".join(f'<div class="card-label"></div>' for _ in range(t["bullets_count"]))
    footer_html = '<div class="card-footer"></div>' if f["enabled"] else ''

    css_rules = [
        f".card-{idx_one} {{",
        "  width:100%; height:100%; position:relative; overflow:hidden;",
        f"  background:{t['card_bg']};",
        f"  border:{t['border']};",
        f"  border-radius:{radius};",
        f"  display:flex; flex-direction:column;",
    ]
    if clip:
        css_rules.append(f"  clip-path:{clip};")
    css_rules.append("}")

    css_rules += [
        f".card-{idx_one} .card-header {{",
        f"  background:{h['bg']}; color:{h['text']};",
        f"  padding:{header_padding};",
        f"  font-weight:{h['weight']}; font-size:{h['size_rem']}rem;",
        f"  min-height:{h['height_pct']}%;",
        "  display:flex; align-items:center; gap:0.4rem;",
        "  flex:0 0 auto;",
        "}",
        f".card-{idx_one} .card-value {{",
        "  font-weight:inherit; font-size:inherit;",
        "}",
        f".card-{idx_one} .card-icon {{",
        f"  color:{h['text']}; font-size:{h['size_rem']}rem;",
        "  display:inline-flex; align-items:center;",
        "}",
        f".card-{idx_one} .card-body {{",
        f"  background:{b['bg']}; color:{b['text']};",
        f"  padding:{body_padding};",
        f"  font-size:{b['size_rem']}rem; line-height:{b['line_height']};",
        "  flex:1 1 auto; display:flex; flex-direction:column; gap:0.45rem;",
        "}",
        f".card-{idx_one} .card-label {{",
        f"  color:{b['text']};",
        "  position:relative; padding-left:0.85em;",
        "}",
        f".card-{idx_one} .card-label::before {{",
        f"  content:'\\2022'; color:{b['text']};",
        "  position:absolute; left:0; top:0;",
        "}",
    ]
    if f["enabled"]:
        css_rules += [
            f".card-{idx_one} .card-footer {{",
            f"  background:{f['bg']}; color:{f['text']};",
            f"  font-weight:{f['weight']}; font-size:{f['size_rem']}rem;",
            f"  padding:{footer_padding}; border-top:{f['border_top']};",
            f"  min-height:{f['height_pct']}%;",
            "  flex:0 0 auto; display:flex; align-items:center;",
            "}",
        ]

    css = "<style>\n" + "\n".join(css_rules) + "\n</style>"
    body_inner = (
        f'<div class="card-{idx_one}">'
        f'  <div class="card-header">{icon_html}<div class="card-value"></div></div>'
        f'  <div class="card-body">{bullet_divs}</div>'
        f'  {footer_html}'
        f'</div>'
    )
    return css + body_inner


def is_uniform_grid_layout(layout_type: str, slide_type: str) -> bool:
    """Layouts where every card is structurally identical → templating wins.

    Excludes hub_spoke (center+spokes asymmetry), comparison (left vs right
    asymmetry), pyramid (size gradient), stats_hero (hero + small stats).
    """
    sl = (slide_type or "").lower()
    lt = (layout_type or "").lower()
    if sl in ("roadmap", "timeline", "process_flow", "feature_grid"):
        return True
    if sl == "dashboard" and lt in ("horizontal_row", "grid"):
        return True
    return False
