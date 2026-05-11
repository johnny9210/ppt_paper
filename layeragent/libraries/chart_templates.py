"""Chart-type deterministic renderers — same pattern as card_templates.

For consulting-style slides (bar / line / waterfall / matrix_2x2 / mekko /
harvey_table_advanced), the structure is data-driven: bar heights = values,
positions = data plotting, not free-form card layouts. Rendering these
through the card pipeline (chat_parser → analyzer → card_detail) produces
the failures the user observed (bars-as-cards, line collapsed to hero,
matrix scattered, mekko spaghetti).

Each renderer here:
  - takes the slide's parsed content + palette
  - returns a full-slide HTML fragment that fills the slide area
  - bypasses card_detail entirely (analyzer empties cards for chart slides)

Stage 1 (POC): bar_chart only. Validate that the templating pattern that
worked for process_flow (deterministic geometry + slot fills via
text_inserter) extends to chart slides. Then expand to line/matrix/etc.
"""
from __future__ import annotations

import html as _html


def _esc(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


def _parse_num(v) -> float | None:
    """'$480M' / '+23%' / '128억' → numeric."""
    import re
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").strip().replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    n = float(m.group())
    # crude unit suffix handling
    if "조" in s: n *= 1e12
    elif "억" in s: n *= 1e8
    elif "만" in s: n *= 1e4
    return n


def render_bar_chart(content: dict, palette: dict) -> str:
    """McKinsey-style vertical bar chart, deterministic SVG.

    Expected content schema (chat_parser emits):
      {
        "title": str,
        "subtitle": str (optional),
        "y_axis_label": str (optional, e.g. "$M"),
        "bars": [
          {"label": "BU1", "value": "$480M", "plan": "$420M" (optional),
           "highlight": true/false (optional — gray bar for below-plan)},
          ...
        ],
        "source": str (optional)
      }
    """
    title = content.get("title", "")
    subtitle = content.get("subtitle", "") or content.get("description", "")
    y_label = content.get("y_axis_label", "") or content.get("axis_label", "")
    bars = content.get("bars") or content.get("items") or []
    source = content.get("source", "")

    # Resolve colors. Default to McKinsey navy + neutral gray.
    accent = palette.get("accent") or palette.get("bg_primary") or "#1F3864"
    text_dark = palette.get("text_bright") or "#1A2230"
    if not text_dark.startswith("#") or len(text_dark) != 7:
        text_dark = "#1A2230"
    # Below-plan / muted color = light gray
    muted = "#B8BDC4"
    grid = "rgba(0,0,0,0.08)"
    axis_text = "#6B7280"

    if not bars:
        return ""

    # Parse numeric values
    vals = []
    plans = []
    labels = []
    val_texts = []
    plan_texts = []
    highlights = []
    for b in bars:
        v = _parse_num(b.get("value"))
        p = _parse_num(b.get("plan"))
        vals.append(v if v is not None else 0.0)
        plans.append(p)
        labels.append(str(b.get("label") or b.get("name") or ""))
        val_texts.append(str(b.get("value") or ""))
        plan_texts.append(str(b.get("plan") or "") if b.get("plan") is not None else "")
        # explicit highlight flag wins; else infer below-plan = muted
        h = b.get("highlight")
        if h is None:
            h = True if (p is not None and v is not None and v >= p) else (p is None)
        highlights.append(bool(h))

    vmax = max([v for v in vals + [p for p in plans if p is not None] if v is not None] + [1])
    # Round vmax up to a nice tick (e.g., 500 instead of 480)
    import math
    tick_unit = 10 ** (math.floor(math.log10(vmax)))
    nice_max = math.ceil(vmax / tick_unit) * tick_unit
    if nice_max < vmax * 1.05:
        nice_max += tick_unit

    n = len(bars)
    # SVG layout (in svg user units; scaled to slide bbox via container)
    svg_w = 1200
    svg_h = 540
    plot_left = 90
    plot_right = 40
    plot_top = 30
    plot_bottom = 70
    pw = svg_w - plot_left - plot_right
    ph = svg_h - plot_top - plot_bottom
    bar_w = pw / (n * 1.6)
    gap = bar_w * 0.6
    total_bars_width = n * bar_w + (n - 1) * gap
    x0 = plot_left + (pw - total_bars_width) / 2

    # Y axis ticks
    n_ticks = 5
    ticks_svg = []
    for i in range(n_ticks + 1):
        y_val = nice_max * i / n_ticks
        y = plot_top + ph - (y_val / nice_max) * ph
        ticks_svg.append(
            f'<line x1="{plot_left}" y1="{y:.1f}" x2="{svg_w - plot_right}" y2="{y:.1f}" '
            f'stroke="{grid}" stroke-width="1"/>'
        )
        ticks_svg.append(
            f'<text x="{plot_left - 10}" y="{y + 4:.1f}" text-anchor="end" '
            f'fill="{axis_text}" font-size="14" font-family="Noto Sans KR,sans-serif">'
            f'{int(y_val) if y_val == int(y_val) else round(y_val, 1)}</text>'
        )

    # Y axis label
    y_axis_html = ""
    if y_label:
        y_axis_html = (
            f'<text x="{plot_left - 30}" y="{plot_top - 8}" text-anchor="middle" '
            f'fill="{axis_text}" font-size="14" font-weight="600" '
            f'font-family="Noto Sans KR,sans-serif">{_esc(y_label)}</text>'
        )

    # Bars
    bars_svg = []
    for i, (v, p, lbl, vtxt, ptxt, hl) in enumerate(
        zip(vals, plans, labels, val_texts, plan_texts, highlights)
    ):
        x = x0 + i * (bar_w + gap)
        bh = (v / nice_max) * ph if v else 0
        y_top = plot_top + ph - bh
        color = accent if hl else muted
        bars_svg.append(
            f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
            f'fill="{color}"/>'
        )
        # Value label above bar (actual value text)
        if vtxt:
            bars_svg.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{y_top - 10:.1f}" '
                f'text-anchor="middle" fill="{text_dark}" font-size="16" font-weight="700" '
                f'font-family="Noto Sans KR,sans-serif">{_esc(vtxt)}</text>'
            )
        # Plan dashed line + label inside bar (McKinsey convention)
        if p is not None:
            py = plot_top + ph - (p / nice_max) * ph
            bars_svg.append(
                f'<line x1="{x - 4:.1f}" y1="{py:.1f}" x2="{x + bar_w + 4:.1f}" y2="{py:.1f}" '
                f'stroke="#FFFFFF" stroke-width="2" stroke-dasharray="4 3" opacity="0.9"/>'
            )
            if ptxt:
                bars_svg.append(
                    f'<text x="{x + bar_w / 2:.1f}" y="{py + 18:.1f}" '
                    f'text-anchor="middle" fill="#FFFFFF" font-size="13" '
                    f'font-family="Noto Sans KR,sans-serif" opacity="0.95">{_esc(ptxt)}</text>'
                )
        # X axis label
        bars_svg.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{plot_top + ph + 24:.1f}" '
            f'text-anchor="middle" fill="{text_dark}" font-size="15" font-weight="600" '
            f'font-family="Noto Sans KR,sans-serif">{_esc(lbl)}</text>'
        )

    # X axis base line
    bars_svg.append(
        f'<line x1="{plot_left}" y1="{plot_top + ph}" x2="{svg_w - plot_right}" '
        f'y2="{plot_top + ph}" stroke="{text_dark}" stroke-width="1.5"/>'
    )

    title_html = ""
    if title:
        title_html = (
            f'<div style="font-size:1.75rem;font-weight:700;color:{text_dark};'
            f'font-family:Noto Sans KR,sans-serif;line-height:1.25;">{_esc(title)}</div>'
        )
    if subtitle:
        title_html += (
            f'<div style="font-size:1rem;color:{axis_text};margin-top:4px;'
            f'font-family:Noto Sans KR,sans-serif;">{_esc(subtitle)}</div>'
        )

    source_html = ""
    if source:
        source_html = (
            f'<div style="position:absolute;right:3%;bottom:1.5%;font-size:0.7rem;'
            f'color:{axis_text};font-family:Noto Sans KR,sans-serif;">{_esc(source)}</div>'
        )

    return f'''
<div style="position:absolute;left:4%;top:4%;right:4%;font-family:Noto Sans KR,sans-serif;">
  {title_html}
</div>
<div style="position:absolute;left:3%;right:3%;top:22%;bottom:8%;">
  <svg viewBox="0 0 {svg_w} {svg_h}" preserveAspectRatio="xMidYMid meet"
       style="width:100%;height:100%;">
    {y_axis_html}
    {''.join(ticks_svg)}
    {''.join(bars_svg)}
  </svg>
</div>
{source_html}
'''.strip()


# ──────────────────────────────────────────────────────────────────────
# line_chart — McKinsey-style time-series with annotated callouts
# ──────────────────────────────────────────────────────────────────────

def render_line_chart(content: dict, palette: dict) -> str:
    """Multi-series line chart with legend + per-series end-of-line labels.

    Schema (preferred — multi-series):
      {title, subtitle, y_axis_label, x_axis_label,
       series: [{
         "name": "Our Firm", "color": "#22A45D" (optional), "highlight": true|false,
         "points": [{"x_label": "Q1 Y1", "y_value": "18%",
                     "annotation": "..." (optional callout)}]
       }],
       source}

    Back-compat (single series): {title, subtitle, points: [...], ...}
    """
    title = content.get("title", "")
    subtitle = content.get("subtitle", "") or content.get("description", "")
    y_label = content.get("y_axis_label", "")
    x_label = content.get("x_axis_label", "")
    source = content.get("source", "")

    # Normalize to series list. Single-series legacy → wrap into one series.
    series = content.get("series")
    if not series:
        legacy_points = content.get("points") or content.get("items") or []
        if legacy_points:
            series = [{"name": "", "highlight": True, "points": legacy_points}]
        else:
            series = []
    if not series:
        return ""

    accent = palette.get("accent") or "#1F3864"
    text_dark = palette.get("text_bright") if (palette.get("text_bright") or "").startswith("#") else "#1A2230"
    axis_text = "#6B7280"
    grid = "rgba(0,0,0,0.08)"
    # Default colors for non-highlight series — neutral grays in decreasing
    # darkness so multiple competitors fade behind the highlighted line.
    neutral_grays = ["#404040", "#808080", "#B0B0B0", "#CCCCCC"]

    import math
    # X-axis: take the longest series' x_labels as the canonical axis
    primary = max(series, key=lambda s: len(s.get("points") or []))
    x_labels = [str(p.get("x_label") or "") for p in (primary.get("points") or [])]
    n_x = len(x_labels)
    if n_x == 0:
        return ""

    # Y range over all series' values
    all_vals = []
    for s in series:
        for p in (s.get("points") or []):
            v = _parse_num(p.get("y_value"))
            if v is not None:
                all_vals.append(v)
    if not all_vals:
        return ""
    vmax = max(all_vals + [1])
    vmin = min(all_vals + [0])
    tick_unit = 10 ** math.floor(math.log10(max(vmax, 1)))
    nice_max = math.ceil(vmax / tick_unit) * tick_unit
    if nice_max < vmax * 1.05:
        nice_max += tick_unit
    nice_min = 0 if vmin >= 0 else math.floor(vmin / tick_unit) * tick_unit

    svg_w, svg_h = 1200, 540
    has_legend = len(series) > 1 or any(s.get("name") for s in series)
    plot_left, plot_right, plot_top, plot_bottom = 100, (220 if has_legend else 80), 50, 80
    pw = svg_w - plot_left - plot_right
    ph = svg_h - plot_top - plot_bottom

    def px(i): return plot_left + (i / max(n_x - 1, 1)) * pw
    def py(v): return plot_top + ph - ((v - nice_min) / (nice_max - nice_min) * ph)

    # Grid + Y ticks
    n_ticks = 4
    grid_svg = []
    for i in range(n_ticks + 1):
        yv = nice_min + (nice_max - nice_min) * i / n_ticks
        y = py(yv)
        grid_svg.append(f'<line x1="{plot_left}" y1="{y:.1f}" x2="{svg_w - plot_right}" y2="{y:.1f}" stroke="{grid}" stroke-width="1"/>')
        tt = int(yv) if yv == int(yv) else round(yv, 1)
        grid_svg.append(f'<text x="{plot_left - 12}" y="{y + 4:.1f}" text-anchor="end" fill="{axis_text}" font-size="14" font-family="Noto Sans KR,sans-serif">{tt}{"%" if vmax<=100 and "%" in (str(primary.get("points",[{}])[0].get("y_value","")) if primary.get("points") else "") else ""}</text>')

    # X labels (under axis)
    x_lbl_svg = []
    for i, lbl in enumerate(x_labels):
        x_lbl_svg.append(
            f'<text x="{px(i):.1f}" y="{plot_top + ph + 22:.1f}" text-anchor="middle" '
            f'fill="{text_dark}" font-size="13" font-family="Noto Sans KR,sans-serif">{_esc(lbl)}</text>'
        )

    # Series rendering — highlight on top, neutrals behind
    neutral_idx = 0
    series_sorted = sorted(enumerate(series), key=lambda kv: 1 if kv[1].get("highlight") else 0)
    series_svg = []
    legend_svg = []
    end_labels_svg = []
    anno_svg = []

    for orig_idx, s in series_sorted:
        pts = s.get("points") or []
        if not pts:
            continue
        is_hl = bool(s.get("highlight"))
        color = s.get("color")
        if not color or not str(color).startswith("#"):
            color = accent if is_hl else neutral_grays[neutral_idx % len(neutral_grays)]
            if not is_hl:
                neutral_idx += 1
        stroke_w = 4 if is_hl else 2.5
        opacity = 1.0 if is_hl else 0.9

        # Build polyline points only for points that exist in canonical x axis
        pts_pairs = []
        for j, p in enumerate(pts):
            v = _parse_num(p.get("y_value"))
            if v is None:
                continue
            pts_pairs.append((j, v))
        if not pts_pairs:
            continue
        path = " ".join(f"{px(j):.1f},{py(v):.1f}" for j, v in pts_pairs)
        series_svg.append(
            f'<polyline points="{path}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke_w}" stroke-linejoin="round" stroke-linecap="round" '
            f'opacity="{opacity}"/>'
        )
        # Dots only on highlight series (else clutter)
        if is_hl:
            for j, v in pts_pairs:
                series_svg.append(f'<circle cx="{px(j):.1f}" cy="{py(v):.1f}" r="5" fill="{color}"/>')

        # End-of-line value label
        last_j, last_v = pts_pairs[-1]
        last_label = str(pts[last_j].get("y_value") or last_v)
        # Combine value + last x_label as McKinsey convention "27% (Q4 Y3)"
        last_x = x_labels[last_j] if last_j < len(x_labels) else ""
        if last_x:
            label_text = f"{last_label} ({last_x})"
        else:
            label_text = last_label
        end_labels_svg.append(
            f'<text x="{px(last_j) + 10:.1f}" y="{py(last_v) + 5:.1f}" '
            f'fill="{color}" font-size="14" font-weight="{700 if is_hl else 500}" '
            f'font-family="Noto Sans KR,sans-serif">{_esc(label_text)}</text>'
        )

        # Annotations on highlight series
        if is_hl:
            for j, p in enumerate(pts):
                ann = (p.get("annotation") or "").strip()
                if not ann:
                    continue
                v = _parse_num(p.get("y_value")) or 0
                cx = px(j); cy = py(v)
                bx = cx + (30 if j < n_x / 2 else -130)
                by = cy - 60
                bw, bh = 110, 38
                anno_svg.append(
                    f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{(bx+bw/2):.1f}" y2="{by+bh:.1f}" stroke="{color}" stroke-width="1"/>'
                )
                anno_svg.append(
                    f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw}" height="{bh}" rx="4" fill="{color}"/>'
                )
                anno_svg.append(
                    f'<text x="{(bx+bw/2):.1f}" y="{by+bh/2+4:.1f}" text-anchor="middle" '
                    f'fill="#FFFFFF" font-size="12" font-family="Noto Sans KR,sans-serif">{_esc(ann[:28])}</text>'
                )

    # Legend (right side)
    if has_legend:
        lx = svg_w - plot_right + 20
        ly = plot_top + 20
        # Preserve original series order in legend
        line_h = 28
        for i, s in enumerate(series):
            color = s.get("color")
            if not color or not str(color).startswith("#"):
                color = accent if s.get("highlight") else neutral_grays[i % len(neutral_grays)]
            name = str(s.get("name") or f"Series {i+1}")
            y = ly + i * line_h
            weight = 700 if s.get("highlight") else 500
            legend_svg.append(
                f'<rect x="{lx}" y="{y-10}" width="18" height="14" fill="{color}"/>'
                f'<text x="{lx+26}" y="{y+2}" fill="{text_dark}" font-size="14" '
                f'font-weight="{weight}" font-family="Noto Sans KR,sans-serif">{_esc(name)}</text>'
            )

    y_axis_html = f'<text x="{plot_left - 60}" y="{plot_top - 12}" fill="{axis_text}" font-size="13" font-family="Noto Sans KR,sans-serif">{_esc(y_label)}</text>' if y_label else ""
    x_axis_html = f'<text x="{plot_left + pw/2:.1f}" y="{svg_h - 18}" text-anchor="middle" fill="{axis_text}" font-size="13" font-family="Noto Sans KR,sans-serif">{_esc(x_label)}</text>' if x_label else ""

    title_html = ""
    if title:
        title_html = f'<div style="font-size:1.75rem;font-weight:700;color:{text_dark};font-family:Noto Sans KR,sans-serif;line-height:1.25;">{_esc(title)}</div>'
    if subtitle:
        title_html += f'<div style="font-size:1rem;color:{axis_text};margin-top:4px;font-family:Noto Sans KR,sans-serif;">{_esc(subtitle)}</div>'
    source_html = f'<div style="position:absolute;right:3%;bottom:1.5%;font-size:0.7rem;color:{axis_text};font-family:Noto Sans KR,sans-serif;">{_esc(source)}</div>' if source else ""

    return f'''
<div style="position:absolute;left:4%;top:4%;right:4%;font-family:Noto Sans KR,sans-serif;">{title_html}</div>
<div style="position:absolute;left:3%;right:3%;top:22%;bottom:8%;">
  <svg viewBox="0 0 {svg_w} {svg_h}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%;">
    {y_axis_html}{x_axis_html}
    {''.join(grid_svg)}
    {''.join(x_lbl_svg)}
    {''.join(series_svg)}
    {''.join(end_labels_svg)}
    {''.join(anno_svg)}
    {''.join(legend_svg)}
  </svg>
</div>
{source_html}
'''.strip()


# ──────────────────────────────────────────────────────────────────────
# tree_diagram — McKinsey-style executive-summary hierarchical tree
# ──────────────────────────────────────────────────────────────────────

def render_tree_diagram(content: dict, palette: dict) -> str:
    """Hierarchical tree: root → N branches → optional leaves under each branch.

    Schema:
      {title, subtitle,
       root: {"label": "Achieve $200M ARR by FY2026"},
       branches: [
         {"label": "Expand APAC presence",
          "leaves": ["Establish regional hub in Singapore",
                     "Localize sales & support in Japan",
                     "Penetrate key growth markets in India"]},
         ...
       ],
       source}
    """
    title = content.get("title", "")
    subtitle = content.get("subtitle", "") or content.get("description", "")
    root = content.get("root") or {}
    branches = content.get("branches") or content.get("nodes") or []
    source = content.get("source", "")

    accent = palette.get("accent") or "#1F3864"
    text_dark = palette.get("text_bright") if (palette.get("text_bright") or "").startswith("#") else "#1A2230"
    axis_text = "#6B7280"

    if not branches:
        return ""

    # Layout
    svg_w, svg_h = 1200, 560
    pad_left, pad_right, pad_top, pad_bot = 30, 30, 30, 60
    grid_w = svg_w - pad_left - pad_right
    grid_h = svg_h - pad_top - pad_bot

    # Levels: root at top (y=10%), branches middle (y=40%), leaves bottom (y=72%)
    root_h = 70
    branch_h = 62
    leaf_h = 64
    root_y = pad_top + 10
    branch_y = pad_top + int(grid_h * 0.35)
    leaf_y = pad_top + int(grid_h * 0.62)

    # Root box (center, ~40% width)
    root_w = min(560, int(grid_w * 0.45))
    root_x = pad_left + (grid_w - root_w) / 2

    # Branch boxes evenly distributed
    n_b = len(branches)
    branch_gap = 16
    branch_w = (grid_w - branch_gap * (n_b - 1)) / max(n_b, 1)
    branch_w = max(160, min(branch_w, 320))
    total_branch = n_b * branch_w + (n_b - 1) * branch_gap
    branch_x0 = pad_left + (grid_w - total_branch) / 2

    svg_parts = []

    # Root box
    svg_parts.append(
        f'<rect x="{root_x:.1f}" y="{root_y:.1f}" width="{root_w}" height="{root_h}" '
        f'fill="#FFFFFF" stroke="{accent}" stroke-width="2"/>'
    )
    svg_parts.append(
        f'<text x="{root_x + root_w/2:.1f}" y="{root_y + root_h/2 + 6:.1f}" '
        f'text-anchor="middle" fill="{text_dark}" font-size="18" font-weight="700" '
        f'font-family="Noto Sans KR,sans-serif">{_esc(str(root.get("label") or ""))}</text>'
    )

    # Connector from root to branches: vertical stem then horizontal bar
    stem_top = root_y + root_h
    stem_bot = branch_y - 12
    stem_x = root_x + root_w / 2
    svg_parts.append(
        f'<line x1="{stem_x:.1f}" y1="{stem_top}" x2="{stem_x:.1f}" y2="{stem_bot}" '
        f'stroke="{accent}" stroke-width="2"/>'
    )

    branch_centers = []
    for i, b in enumerate(branches):
        bx = branch_x0 + i * (branch_w + branch_gap)
        # Branch box
        svg_parts.append(
            f'<rect x="{bx:.1f}" y="{branch_y:.1f}" width="{branch_w:.1f}" height="{branch_h}" '
            f'fill="#FFFFFF" stroke="{accent}" stroke-width="2"/>'
        )
        # Branch label (with wrap to 2 lines if long)
        name = str(b.get("label") or "")
        words = name.split()
        line1, line2 = name, ""
        if len(name) > 22 and len(words) > 1:
            half = len(name) // 2
            best = 0
            for w_i, w in enumerate(words):
                s = " ".join(words[: w_i + 1])
                if len(s) <= half:
                    best = w_i + 1
            line1 = " ".join(words[:best]) or words[0]
            line2 = " ".join(words[best:])
        if line2:
            svg_parts.append(
                f'<text x="{bx + branch_w/2:.1f}" y="{branch_y + branch_h/2 - 4:.1f}" text-anchor="middle" '
                f'fill="{text_dark}" font-size="15" font-weight="600" font-family="Noto Sans KR,sans-serif">{_esc(line1)}</text>'
            )
            svg_parts.append(
                f'<text x="{bx + branch_w/2:.1f}" y="{branch_y + branch_h/2 + 14:.1f}" text-anchor="middle" '
                f'fill="{text_dark}" font-size="15" font-weight="600" font-family="Noto Sans KR,sans-serif">{_esc(line2)}</text>'
            )
        else:
            svg_parts.append(
                f'<text x="{bx + branch_w/2:.1f}" y="{branch_y + branch_h/2 + 5:.1f}" text-anchor="middle" '
                f'fill="{text_dark}" font-size="16" font-weight="600" font-family="Noto Sans KR,sans-serif">{_esc(name)}</text>'
            )
        branch_centers.append(bx + branch_w / 2)

    # Horizontal connector at stem_bot from leftmost branch center to rightmost
    if branch_centers:
        svg_parts.append(
            f'<line x1="{branch_centers[0]:.1f}" y1="{stem_bot}" '
            f'x2="{branch_centers[-1]:.1f}" y2="{stem_bot}" stroke="{accent}" stroke-width="2"/>'
        )
        # Vertical drop from horizontal bar to each branch box top
        for cx in branch_centers:
            svg_parts.append(
                f'<line x1="{cx:.1f}" y1="{stem_bot}" x2="{cx:.1f}" y2="{branch_y}" '
                f'stroke="{accent}" stroke-width="2"/>'
            )

    # Leaves per branch
    for i, b in enumerate(branches):
        leaves = b.get("leaves") or []
        if not leaves:
            continue
        bx = branch_x0 + i * (branch_w + branch_gap)
        bcx = bx + branch_w / 2
        # Stem from branch box to leaves area
        leaf_stem_top = branch_y + branch_h
        leaf_stem_bot = leaf_y - 10
        svg_parts.append(
            f'<line x1="{bcx:.1f}" y1="{leaf_stem_top}" x2="{bcx:.1f}" y2="{leaf_stem_bot}" '
            f'stroke="{accent}" stroke-width="2"/>'
        )
        n_l = len(leaves)
        # Leaves laid out under the branch's width (allow some shrink for many leaves)
        leaf_total_w = branch_w
        leaf_gap = 6
        leaf_w = (leaf_total_w - leaf_gap * (n_l - 1)) / max(n_l, 1)
        leaf_w = max(60, min(leaf_w, 130))
        total_lw = n_l * leaf_w + (n_l - 1) * leaf_gap
        leaf_x0 = bcx - total_lw / 2

        # Horizontal connector across leaves
        leaf_cxs = [leaf_x0 + j * (leaf_w + leaf_gap) + leaf_w / 2 for j in range(n_l)]
        if n_l > 1:
            svg_parts.append(
                f'<line x1="{leaf_cxs[0]:.1f}" y1="{leaf_stem_bot}" '
                f'x2="{leaf_cxs[-1]:.1f}" y2="{leaf_stem_bot}" stroke="{accent}" stroke-width="2"/>'
            )
        for j, leaf in enumerate(leaves):
            lx = leaf_x0 + j * (leaf_w + leaf_gap)
            # Vertical drop
            svg_parts.append(
                f'<line x1="{leaf_cxs[j]:.1f}" y1="{leaf_stem_bot}" x2="{leaf_cxs[j]:.1f}" y2="{leaf_y}" '
                f'stroke="{accent}" stroke-width="2"/>'
            )
            svg_parts.append(
                f'<rect x="{lx:.1f}" y="{leaf_y:.1f}" width="{leaf_w:.1f}" height="{leaf_h}" '
                f'fill="#FFFFFF" stroke="{accent}" stroke-width="2"/>'
            )
            # Leaf text — wrap into up to 3 lines
            txt = str(leaf) if not isinstance(leaf, dict) else str(leaf.get("label") or "")
            # crude wrap by char width
            max_chars = max(8, int(leaf_w / 7))
            words = txt.split()
            lines: list[str] = []
            cur = ""
            for w in words:
                if len(cur) + len(w) + 1 <= max_chars:
                    cur = (cur + " " + w).strip()
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
            lines = lines[:3]
            line_dy = 14
            start_y = leaf_y + leaf_h / 2 - line_dy * (len(lines) - 1) / 2 + 4
            for li, line in enumerate(lines):
                svg_parts.append(
                    f'<text x="{leaf_cxs[j]:.1f}" y="{start_y + li * line_dy:.1f}" text-anchor="middle" '
                    f'fill="{text_dark}" font-size="11" font-family="Noto Sans KR,sans-serif">{_esc(line)}</text>'
                )

    title_html = ""
    if title:
        title_html = f'<div style="font-size:1.75rem;font-weight:700;color:{text_dark};font-family:Noto Sans KR,sans-serif;line-height:1.25;">{_esc(title)}</div>'
    if subtitle:
        title_html += f'<div style="font-size:1rem;color:{axis_text};margin-top:4px;font-family:Noto Sans KR,sans-serif;">{_esc(subtitle)}</div>'
    source_html = f'<div style="position:absolute;right:3%;bottom:1.5%;font-size:0.7rem;color:{axis_text};font-family:Noto Sans KR,sans-serif;">{_esc(source)}</div>' if source else ""

    return f'''
<div style="position:absolute;left:4%;top:4%;right:4%;font-family:Noto Sans KR,sans-serif;">{title_html}</div>
<div style="position:absolute;left:3%;right:3%;top:22%;bottom:8%;">
  <svg viewBox="0 0 {svg_w} {svg_h}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%;">
    {''.join(svg_parts)}
  </svg>
</div>
{source_html}
'''.strip()


# ──────────────────────────────────────────────────────────────────────
# waterfall — cascading deltas with start / +Δ / −Δ / total
# ──────────────────────────────────────────────────────────────────────

def render_waterfall(content: dict, palette: dict) -> str:
    """Schema:
      {title, subtitle, y_axis_label,
       bars: [{"label", "value", "type": "start"|"positive"|"negative"|"total"}],
       source}
    """
    title = content.get("title", "")
    subtitle = content.get("subtitle", "") or content.get("description", "")
    y_label = content.get("y_axis_label", "")
    bars = content.get("bars") or content.get("items") or []
    source = content.get("source", "")

    accent = palette.get("accent") or "#1F3864"
    text_dark = palette.get("text_bright") if (palette.get("text_bright") or "").startswith("#") else "#1A2230"
    pos_color = "#3B7DB7"           # light navy / blue for additions
    neg_color = "#C0392B"            # red for deletions (consulting convention)
    total_color = accent             # dark navy
    axis_text = "#6B7280"
    grid = "rgba(0,0,0,0.08)"

    if not bars:
        return ""

    # Compute running sum & per-bar (y_bottom, y_top) in data space
    running = 0.0
    segments = []   # list of (label, type, value, bottom, top, color, value_text)
    vmin, vmax = 0.0, 0.0
    for b in bars:
        v = _parse_num(b.get("value")) or 0.0
        t = (b.get("type") or "").lower()
        vt = str(b.get("value") or "")
        if t == "start":
            bottom, top = 0.0, v
            running = v
            color = total_color
        elif t == "total":
            bottom, top = 0.0, running
            color = total_color
        elif t == "positive":
            bottom, top = running, running + v
            running += v
            color = pos_color
        elif t == "negative":
            bottom, top = running - v, running
            running -= v
            color = neg_color
        else:
            # treat as positive by default
            bottom, top = running, running + v
            running += v
            color = pos_color
        segments.append((str(b.get("label") or ""), t, v, bottom, top, color, vt))
        vmax = max(vmax, top); vmin = min(vmin, bottom)

    import math
    span = vmax - vmin
    if span <= 0:
        span = 1
    tick_unit = 10 ** math.floor(math.log10(max(vmax, 1)))
    nice_max = math.ceil(vmax / tick_unit) * tick_unit
    nice_min = math.floor(vmin / tick_unit) * tick_unit if vmin < 0 else 0
    nice_span = nice_max - nice_min

    svg_w, svg_h = 1200, 540
    plot_left, plot_right, plot_top, plot_bottom = 100, 60, 30, 80
    pw = svg_w - plot_left - plot_right
    ph = svg_h - plot_top - plot_bottom
    n = len(segments)
    bar_w = pw / (n * 1.5)
    gap = bar_w * 0.5
    total_w = n * bar_w + (n - 1) * gap
    x0 = plot_left + (pw - total_w) / 2

    def py(v): return plot_top + ph - ((v - nice_min) / nice_span) * ph

    # Grid + Y ticks
    grid_svg = []
    n_ticks = 5
    for i in range(n_ticks + 1):
        yv = nice_min + nice_span * i / n_ticks
        y = py(yv)
        grid_svg.append(f'<line x1="{plot_left}" y1="{y:.1f}" x2="{svg_w - plot_right}" y2="{y:.1f}" stroke="{grid}" stroke-width="1"/>')
        grid_svg.append(f'<text x="{plot_left - 12}" y="{y + 4:.1f}" text-anchor="end" fill="{axis_text}" font-size="14" font-family="Noto Sans KR,sans-serif">{int(yv) if yv == int(yv) else round(yv, 1)}</text>')

    bars_svg = []
    prev_top_xy = None
    for i, (lbl, t, v, bottom, top, color, vt) in enumerate(segments):
        x = x0 + i * (bar_w + gap)
        y_top = py(top)
        y_bot = py(bottom)
        bh = abs(y_bot - y_top)
        y_rect = min(y_top, y_bot)
        bars_svg.append(f'<rect x="{x:.1f}" y="{y_rect:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}"/>')
        # Value label above (or below if negative)
        if vt:
            sign = "+" if t == "positive" else ("−" if t == "negative" else "")
            display = sign + vt.lstrip("+-") if t in ("positive", "negative") else vt
            label_y = y_rect - 8 if t != "negative" else (y_bot + 20)
            bars_svg.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{label_y:.1f}" text-anchor="middle" '
                f'fill="{text_dark}" font-size="15" font-weight="700" font-family="Noto Sans KR,sans-serif">{_esc(display)}</text>'
            )
        # X label
        bars_svg.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{plot_top + ph + 24:.1f}" text-anchor="middle" '
            f'fill="{text_dark}" font-size="13" font-family="Noto Sans KR,sans-serif">{_esc(lbl)}</text>'
        )
        # Connector dashed line from prev top to this bar's reference
        if prev_top_xy is not None and t not in ("start",):
            from_x, from_y = prev_top_xy
            to_y = y_bot if t in ("positive", "negative") else y_top
            bars_svg.append(
                f'<line x1="{from_x:.1f}" y1="{from_y:.1f}" x2="{x:.1f}" y2="{to_y:.1f}" '
                f'stroke="{text_dark}" stroke-width="1" stroke-dasharray="4 3" opacity="0.6"/>'
            )
        # Update prev_top_xy for cumulative connector
        prev_top_xy = (x + bar_w, y_top if t != "negative" else y_bot)

    # Baseline at y=0
    bars_svg.append(
        f'<line x1="{plot_left}" y1="{py(0):.1f}" x2="{svg_w - plot_right}" y2="{py(0):.1f}" '
        f'stroke="{text_dark}" stroke-width="1.5"/>'
    )

    y_axis_html = f'<text x="{plot_left - 60}" y="{plot_top - 6}" fill="{axis_text}" font-size="13" font-family="Noto Sans KR,sans-serif">{_esc(y_label)}</text>' if y_label else ""
    title_html = ""
    if title:
        title_html = f'<div style="font-size:1.75rem;font-weight:700;color:{text_dark};font-family:Noto Sans KR,sans-serif;line-height:1.25;">{_esc(title)}</div>'
    if subtitle:
        title_html += f'<div style="font-size:1rem;color:{axis_text};margin-top:4px;font-family:Noto Sans KR,sans-serif;">{_esc(subtitle)}</div>'
    source_html = f'<div style="position:absolute;right:3%;bottom:1.5%;font-size:0.7rem;color:{axis_text};font-family:Noto Sans KR,sans-serif;">{_esc(source)}</div>' if source else ""

    return f'''
<div style="position:absolute;left:4%;top:4%;right:4%;font-family:Noto Sans KR,sans-serif;">{title_html}</div>
<div style="position:absolute;left:3%;right:3%;top:22%;bottom:8%;">
  <svg viewBox="0 0 {svg_w} {svg_h}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%;">
    {y_axis_html}{''.join(grid_svg)}{''.join(bars_svg)}
  </svg>
</div>
{source_html}
'''.strip()


# ──────────────────────────────────────────────────────────────────────
# matrix_2x2 — 4 quadrants with items + optional highlight
# ──────────────────────────────────────────────────────────────────────

_QUADRANT_POSITIONS = {
    "high_left":  (0, 0),   # high impact / low likelihood (top-left)
    "high_right": (1, 0),   # high impact / high likelihood (top-right)
    "low_left":   (0, 1),   # low impact / low likelihood (bottom-left)
    "low_right":  (1, 1),   # low impact / high likelihood (bottom-right)
    "top_left":  (0, 0), "top_right": (1, 0),
    "bottom_left": (0, 1), "bottom_right": (1, 1),
    "tl": (0, 0), "tr": (1, 0), "bl": (0, 1), "br": (1, 1),
}


def render_matrix_2x2(content: dict, palette: dict) -> str:
    """Schema:
      {title, subtitle,
       x_axis: {label: "Likelihood", low: "Low", high: "High"},
       y_axis: {label: "Impact", low: "Low", high: "High"},
       quadrants: [{
          position: "top_left|top_right|bottom_left|bottom_right",
          items: [{name, color (optional hex)}]
       }],
       highlight: "top_right" (optional — draws border + tint),
       source}
    """
    title = content.get("title", "")
    subtitle = content.get("subtitle", "") or content.get("description", "")
    x_axis = content.get("x_axis", {}) or {}
    y_axis = content.get("y_axis", {}) or {}
    quadrants = content.get("quadrants") or []
    highlight = (content.get("highlight") or content.get("highlight_quadrant") or "").lower()
    source = content.get("source", "")

    accent = palette.get("accent") or "#1F3864"
    text_dark = palette.get("text_bright") if (palette.get("text_bright") or "").startswith("#") else "#1A2230"
    axis_text = "#6B7280"
    quad_stroke = "rgba(0,0,0,0.4)"
    highlight_bg = "rgba(31,56,100,0.06)"

    # Layout (in SVG units)
    svg_w, svg_h = 1200, 560
    pad_left, pad_right, pad_top, pad_bot = 110, 60, 30, 80
    qw = (svg_w - pad_left - pad_right) / 2
    qh = (svg_h - pad_top - pad_bot) / 2
    grid_x = pad_left
    grid_y = pad_top

    def q_rect(col, row):
        return (grid_x + col * qw, grid_y + row * qh, qw, qh)

    # Quadrant backgrounds + highlight
    quad_svg = []
    hl_col_row = _QUADRANT_POSITIONS.get(highlight) if highlight else None
    if hl_col_row:
        hx, hy, hw, hh = q_rect(*hl_col_row)
        quad_svg.append(
            f'<rect x="{hx:.1f}" y="{hy:.1f}" width="{hw:.1f}" height="{hh:.1f}" '
            f'fill="{highlight_bg}" stroke="{accent}" stroke-width="2.5"/>'
        )

    # Grid borders
    quad_svg.append(
        f'<rect x="{grid_x:.1f}" y="{grid_y:.1f}" width="{2*qw:.1f}" height="{2*qh:.1f}" '
        f'fill="none" stroke="{quad_stroke}" stroke-width="1.2"/>'
    )
    quad_svg.append(
        f'<line x1="{grid_x + qw:.1f}" y1="{grid_y:.1f}" x2="{grid_x + qw:.1f}" y2="{grid_y + 2 * qh:.1f}" stroke="{quad_stroke}" stroke-width="1"/>'
    )
    quad_svg.append(
        f'<line x1="{grid_x:.1f}" y1="{grid_y + qh:.1f}" x2="{grid_x + 2 * qw:.1f}" y2="{grid_y + qh:.1f}" stroke="{quad_stroke}" stroke-width="1"/>'
    )

    # Items inside each quadrant
    item_svg = []
    for q in quadrants:
        pos = (q.get("position") or "").lower()
        cr = _QUADRANT_POSITIONS.get(pos)
        if not cr:
            continue
        col, row = cr
        qx, qy, qw_, qh_ = q_rect(col, row)
        items = q.get("items") or []
        if not items:
            continue
        # Arrange items in a row, wrap if many
        max_per_row = 3
        n = len(items)
        for i, it in enumerate(items):
            row_in_q = i // max_per_row
            col_in_q = i % max_per_row
            cols_this_row = min(max_per_row, n - row_in_q * max_per_row)
            cx = qx + (col_in_q + 0.5) * (qw_ / cols_this_row)
            rows_needed = math.ceil(n / max_per_row) if False else (n + max_per_row - 1) // max_per_row
            cy = qy + (row_in_q + 0.5) * (qh_ / max(rows_needed, 1))
            color = it.get("color") if it.get("color", "").startswith("#") else accent
            radius = 36
            item_svg.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius}" fill="{color}" stroke="{color}" stroke-width="2"/>'
            )
            name = str(it.get("name") or "")
            # Wrap text into 2 lines of up to 14 chars each
            line1, line2 = name, ""
            if len(name) > 14:
                words = name.split()
                a = ""
                for w in words:
                    if len(a) + len(w) + 1 <= 14:
                        a = (a + " " + w).strip()
                    else:
                        break
                line1 = a or name[:14]
                line2 = name[len(line1):].strip()[:18]
            item_svg.append(
                f'<text x="{cx:.1f}" y="{cy - 2:.1f}" text-anchor="middle" '
                f'fill="#FFFFFF" font-size="11" font-weight="600" font-family="Noto Sans KR,sans-serif">{_esc(line1)}</text>'
            )
            if line2:
                item_svg.append(
                    f'<text x="{cx:.1f}" y="{cy + 12:.1f}" text-anchor="middle" '
                    f'fill="#FFFFFF" font-size="11" font-family="Noto Sans KR,sans-serif">{_esc(line2)}</text>'
                )

    # Axis labels
    axis_svg = []
    if y_axis.get("label"):
        axis_svg.append(
            f'<text x="{pad_left - 70}" y="{grid_y + qh:.1f}" text-anchor="middle" '
            f'fill="{text_dark}" font-size="15" font-weight="700" font-family="Noto Sans KR,sans-serif" '
            f'transform="rotate(-90 {pad_left - 70} {grid_y + qh:.1f})">{_esc(y_axis["label"])}</text>'
        )
    if x_axis.get("label"):
        axis_svg.append(
            f'<text x="{grid_x + qw:.1f}" y="{grid_y + 2 * qh + 56:.1f}" text-anchor="middle" '
            f'fill="{text_dark}" font-size="15" font-weight="700" font-family="Noto Sans KR,sans-serif">{_esc(x_axis["label"])}</text>'
        )
    # Low/High end labels
    for txt, x, y in [
        (y_axis.get("high", ""), pad_left - 30, grid_y + 12),
        (y_axis.get("low", ""),  pad_left - 30, grid_y + 2 * qh - 4),
        (x_axis.get("low", ""),  grid_x + 6, grid_y + 2 * qh + 28),
        (x_axis.get("high", ""), grid_x + 2 * qw - 6, grid_y + 2 * qh + 28),
    ]:
        if txt:
            anchor = "end" if x > grid_x + qw else "start"
            axis_svg.append(
                f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
                f'fill="{axis_text}" font-size="13" font-family="Noto Sans KR,sans-serif">{_esc(txt)}</text>'
            )

    title_html = ""
    if title:
        title_html = f'<div style="font-size:1.75rem;font-weight:700;color:{text_dark};font-family:Noto Sans KR,sans-serif;line-height:1.25;">{_esc(title)}</div>'
    if subtitle:
        title_html += f'<div style="font-size:1rem;color:{axis_text};margin-top:4px;font-family:Noto Sans KR,sans-serif;">{_esc(subtitle)}</div>'
    source_html = f'<div style="position:absolute;right:3%;bottom:1.5%;font-size:0.7rem;color:{axis_text};font-family:Noto Sans KR,sans-serif;">{_esc(source)}</div>' if source else ""

    return f'''
<div style="position:absolute;left:4%;top:4%;right:4%;font-family:Noto Sans KR,sans-serif;">{title_html}</div>
<div style="position:absolute;left:3%;right:3%;top:22%;bottom:8%;">
  <svg viewBox="0 0 {svg_w} {svg_h}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%;">
    {''.join(quad_svg)}{''.join(item_svg)}{''.join(axis_svg)}
  </svg>
</div>
{source_html}
'''.strip()


# ──────────────────────────────────────────────────────────────────────
# mekko (marimekko) — variable-width columns with stacked segments
# ──────────────────────────────────────────────────────────────────────

def render_mekko(content: dict, palette: dict) -> str:
    """Schema:
      {title, subtitle,
       columns: [{
          label: "APAC",
          width_pct: 45,                            // share of x-axis
          segments: [{"label": "Apparel", "value": "$35.2B", "color": "#1F3864" (opt)}],
          footer: "45%" (optional, shown under column label)
       }],
       source}
    """
    title = content.get("title", "")
    subtitle = content.get("subtitle", "") or content.get("description", "")
    columns = content.get("columns") or content.get("items") or []
    source = content.get("source", "")

    accent = palette.get("accent") or "#1F3864"
    text_dark = palette.get("text_bright") if (palette.get("text_bright") or "").startswith("#") else "#1A2230"
    axis_text = "#6B7280"

    if not columns:
        return ""

    # Color shading per column position
    shades = ["#1F3864", "#9AA0A6", "#B7BCC3", "#D4D7DB"]

    # Normalize column widths to sum to 100
    raw_w = [_parse_num(c.get("width_pct")) or 0 for c in columns]
    total_w = sum(raw_w) or len(columns)
    col_w_pct = [w / total_w * 100 for w in raw_w] if total_w else [100 / len(columns)] * len(columns)

    svg_w, svg_h = 1200, 520
    pad_left, pad_right, pad_top, pad_bot = 40, 40, 30, 80
    pw = svg_w - pad_left - pad_right
    ph = svg_h - pad_top - pad_bot

    cols_svg = []
    x_cursor = pad_left
    for ci, col in enumerate(columns):
        cw = pw * col_w_pct[ci] / 100
        segs = col.get("segments") or []
        seg_vals = [_parse_num(s.get("value")) or 0 for s in segs]
        total = sum(seg_vals) or 1
        y_cursor = pad_top
        seg_color = col.get("color") if (col.get("color") or "").startswith("#") else (shades[ci] if ci < len(shades) else accent)
        for si, s in enumerate(segs):
            v = seg_vals[si]
            sh = ph * (v / total)
            color = s.get("color") if (s.get("color") or "").startswith("#") else seg_color
            cols_svg.append(
                f'<rect x="{x_cursor:.1f}" y="{y_cursor:.1f}" width="{cw:.1f}" height="{sh:.1f}" '
                f'fill="{color}" stroke="#FFFFFF" stroke-width="2"/>'
            )
            # Segment label (white text, 2 lines: label + value)
            tx = x_cursor + cw / 2
            ty_mid = y_cursor + sh / 2
            text_color = "#FFFFFF" if _parse_num(color[1:3]) is not None and int(color[1:3], 16) < 180 else "#1A2230"
            lbl = str(s.get("label") or "")
            val = str(s.get("value") or "")
            if sh > 28:
                cols_svg.append(
                    f'<text x="{tx:.1f}" y="{ty_mid - 4:.1f}" text-anchor="middle" fill="{text_color}" '
                    f'font-size="14" font-weight="600" font-family="Noto Sans KR,sans-serif">{_esc(lbl)}</text>'
                )
                cols_svg.append(
                    f'<text x="{tx:.1f}" y="{ty_mid + 14:.1f}" text-anchor="middle" fill="{text_color}" '
                    f'font-size="13" font-family="Noto Sans KR,sans-serif">{_esc(val)}</text>'
                )
            y_cursor += sh

        # Column header (x-axis label)
        col_label = str(col.get("label") or "")
        col_footer = str(col.get("footer") or "")
        cols_svg.append(
            f'<text x="{x_cursor + cw / 2:.1f}" y="{svg_h - pad_bot + 24:.1f}" text-anchor="middle" '
            f'fill="{text_dark}" font-size="15" font-weight="600" font-family="Noto Sans KR,sans-serif">{_esc(col_label)}</text>'
        )
        if col_footer:
            cols_svg.append(
                f'<text x="{x_cursor + cw / 2:.1f}" y="{svg_h - pad_bot + 44:.1f}" text-anchor="middle" '
                f'fill="{axis_text}" font-size="13" font-family="Noto Sans KR,sans-serif">{_esc(col_footer)}</text>'
            )
        x_cursor += cw

    title_html = ""
    if title:
        title_html = f'<div style="font-size:1.75rem;font-weight:700;color:{text_dark};font-family:Noto Sans KR,sans-serif;line-height:1.25;">{_esc(title)}</div>'
    if subtitle:
        title_html += f'<div style="font-size:1rem;color:{axis_text};margin-top:4px;font-family:Noto Sans KR,sans-serif;">{_esc(subtitle)}</div>'
    source_html = f'<div style="position:absolute;right:3%;bottom:1.5%;font-size:0.7rem;color:{axis_text};font-family:Noto Sans KR,sans-serif;">{_esc(source)}</div>' if source else ""

    return f'''
<div style="position:absolute;left:4%;top:4%;right:4%;font-family:Noto Sans KR,sans-serif;">{title_html}</div>
<div style="position:absolute;left:3%;right:3%;top:22%;bottom:8%;">
  <svg viewBox="0 0 {svg_w} {svg_h}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%;">
    {''.join(cols_svg)}
  </svg>
</div>
{source_html}
'''.strip()


# ──────────────────────────────────────────────────────────────────────
# harvey_table_advanced — criteria × options with Harvey balls
# ──────────────────────────────────────────────────────────────────────

def _harvey_ball(fill_pct: float, color: str, size: int = 22) -> str:
    """SVG Harvey ball with fractional fill (0/25/50/75/100)."""
    p = max(0, min(100, fill_pct))
    r = size / 2
    cx = cy = r
    # Empty ring
    base = f'<circle cx="{cx}" cy="{cy}" r="{r - 1}" fill="#FFFFFF" stroke="{color}" stroke-width="1.5"/>'
    if p <= 0:
        wedge = ""
    elif p >= 100:
        wedge = f'<circle cx="{cx}" cy="{cy}" r="{r - 1}" fill="{color}"/>'
    else:
        # Build a pie wedge from 12 o'clock for p% of the circle
        import math
        angle = (p / 100) * 360
        rad = math.radians(angle - 90)
        x2 = cx + (r - 1) * math.cos(rad)
        y2 = cy + (r - 1) * math.sin(rad)
        large = 1 if angle > 180 else 0
        wedge = f'<path d="M {cx} {cy} L {cx} {cy - (r - 1)} A {r - 1} {r - 1} 0 {large} 1 {x2:.2f} {y2:.2f} Z" fill="{color}"/>'
    return f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">{base}{wedge}</svg>'


def render_harvey_table_advanced(content: dict, palette: dict) -> str:
    """Schema:
      {title, subtitle,
       criteria: [{"name": "Cost", "weight_pct": 5}],
       options: [{"name": "Option A", "highlight": false}],
       cells: [   // criteria × options matrix
         [{"fill_pct": 75, "text": "High initial investment"}, ...]
       ],
       source}
    """
    title = content.get("title", "")
    subtitle = content.get("subtitle", "") or content.get("description", "")
    criteria = content.get("criteria") or []
    options = content.get("options") or []
    cells = content.get("cells") or []
    source = content.get("source", "")

    accent = palette.get("accent") or "#1F3864"
    text_dark = palette.get("text_bright") if (palette.get("text_bright") or "").startswith("#") else "#1A2230"
    axis_text = "#6B7280"
    border = "rgba(0,0,0,0.08)"

    if not criteria or not options or not cells:
        return ""

    # Build HTML table (easier than SVG for text wrapping)
    n_cols = len(options)
    crit_col_w = 18
    opt_col_w = (100 - crit_col_w) / max(n_cols, 1)

    # Header row
    header_cells = '<td style="padding:8px 12px;"></td>'
    for opt in options:
        is_hl = bool(opt.get("highlight"))
        style = (
            f"padding:10px 12px;font-weight:700;color:{accent};font-size:14px;"
            f"text-align:left;border-bottom:1.5px solid {accent if is_hl else border};"
        )
        if is_hl:
            style += f"box-shadow:inset 0 0 0 2px {accent};background:rgba(31,56,100,0.03);"
        header_cells += f'<td style="{style};width:{opt_col_w:.1f}%;">{_esc(opt.get("name") or "")}</td>'

    # Body rows
    body_rows = []
    for ci, crit in enumerate(criteria):
        row_cells = []
        crit_text = str(crit.get("name") or "")
        weight = crit.get("weight_pct")
        weight_txt = f' ({weight}%)' if weight is not None else ''
        row_cells.append(
            f'<td style="padding:10px 12px;color:{text_dark};font-weight:700;font-size:13px;'
            f'border-bottom:1px solid {border};width:{crit_col_w}%;">'
            f'{_esc(crit_text)}<span style="color:{axis_text};font-weight:500;">{_esc(weight_txt)}</span></td>'
        )
        for oi, opt in enumerate(options):
            cell = (cells[ci][oi] if ci < len(cells) and oi < len(cells[ci]) else {}) or {}
            fill = _parse_num(cell.get("fill_pct"))
            if fill is None:
                fill = 50
            text = str(cell.get("text") or "")
            is_hl = bool(opt.get("highlight"))
            border_style = f"box-shadow:inset 0 0 0 2px {accent};background:rgba(31,56,100,0.03);" if is_hl else ""
            ball = _harvey_ball(fill, accent, size=22)
            row_cells.append(
                f'<td style="padding:8px 12px;color:{text_dark};font-size:12px;line-height:1.35;'
                f'border-bottom:1px solid {border};vertical-align:top;{border_style}">'
                f'<div style="display:flex;gap:8px;align-items:flex-start;">'
                f'<div style="flex:0 0 auto;margin-top:2px;">{ball}</div>'
                f'<div style="flex:1 1 auto;">{_esc(text)}</div>'
                f'</div></td>'
            )
        body_rows.append(f'<tr>{"".join(row_cells)}</tr>')

    table_html = (
        f'<table style="width:100%;border-collapse:collapse;font-family:Noto Sans KR,sans-serif;">'
        f'<thead><tr>{header_cells}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        f'</table>'
    )

    title_html = ""
    if title:
        title_html = f'<div style="font-size:1.75rem;font-weight:700;color:{text_dark};font-family:Noto Sans KR,sans-serif;line-height:1.25;">{_esc(title)}</div>'
    if subtitle:
        title_html += f'<div style="font-size:1rem;color:{axis_text};margin-top:4px;font-family:Noto Sans KR,sans-serif;">{_esc(subtitle)}</div>'
    source_html = f'<div style="position:absolute;right:3%;bottom:1.5%;font-size:0.7rem;color:{axis_text};font-family:Noto Sans KR,sans-serif;">{_esc(source)}</div>' if source else ""

    return f'''
<div style="position:absolute;left:4%;top:4%;right:4%;font-family:Noto Sans KR,sans-serif;">{title_html}</div>
<div style="position:absolute;left:3%;right:3%;top:22%;bottom:8%;overflow:hidden;">{table_html}</div>
{source_html}
'''.strip()


# ──────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────

import math  # used by matrix_2x2 wrapping math


def is_chart_slide_type(slide_type: str) -> bool:
    """Whether to bypass the card pipeline entirely and use a chart renderer."""
    return (slide_type or "").lower() in (
        "bar_chart",
        "line_chart",
        "waterfall",
        "matrix_2x2",
        "mekko",
        "harvey_table_advanced",
        "tree_diagram",
    )


CHART_RENDERERS = {
    "bar_chart": render_bar_chart,
    "line_chart": render_line_chart,
    "waterfall": render_waterfall,
    "matrix_2x2": render_matrix_2x2,
    "mekko": render_mekko,
    "harvey_table_advanced": render_harvey_table_advanced,
    "tree_diagram": render_tree_diagram,
}


def render_chart_slide(slide_type: str, content: dict, palette: dict) -> str:
    fn = CHART_RENDERERS.get((slide_type or "").lower())
    if not fn:
        return ""
    return fn(content, palette)
