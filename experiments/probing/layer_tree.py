"""Layer tree extraction — from VLM perception (image) and from generated HTML.

A "layer tree" is a normalized representation of a slide's stacking structure:
  [
    {"z": 0, "type": "background", "label": "gradient", "elements": [...]},
    {"z": 1, "type": "card", "label": "glass card 1", "elements": [...]},
    ...
  ]

Trees from both modalities (perception via VLM description, generation via
HTML parse) live in the same namespace, so we can compute LTED between them.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


# Canonical layer types — VLM descriptions and HTML class names normalize to these
LAYER_TYPES = {
    "background", "atmosphere", "decoration",
    "card", "panel",
    "hero", "title",
    "text", "label", "value",
    "icon", "badge", "image",
    "chart", "table",
    "connector", "line", "arrow",
}

_TYPE_ALIASES = {
    "bg": "background", "back": "background", "gradient": "background",
    "glass": "card", "tile": "card", "box": "card",
    "header": "title", "heading": "title", "headline": "title",
    "body": "text", "description": "text", "subtitle": "text", "content": "text",
    "metric": "value", "number": "value",
    "logo": "icon", "symbol": "icon", "emoji": "icon", "shape": "icon",
    "graph": "chart",
    "container": "panel",
    "edge": "connector",
}


@dataclass
class LayerNode:
    """One layer in a tree."""
    z: int
    type: str
    count: int = 1
    children: list["LayerNode"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"z": self.z, "type": self.type, "count": self.count,
                "children": [c.to_dict() for c in self.children]}


# ─────────────────────────────────────────────────────────────────
# Path 1 — Tree from VLM perception (natural-language description)
# ─────────────────────────────────────────────────────────────────

PERCEPTION_PROMPT = """Examine this slide image carefully. List every visual layer
you see, in z-order from back (z=0) to front. For each layer, output ONE line:

  z={N}: type={canonical_type}, count={how_many_instances}, label={short description}

Use these canonical types only:
  background, atmosphere, decoration,
  card, panel, container,
  hero, title, headline,
  content, text, label, value,
  icon, badge, image,
  chart, graph, table,
  connector, line, arrow

Output ONLY the lines, no preamble, no commentary. One layer per line.
"""


def normalize_type(raw: str) -> str | None:
    raw = raw.strip().lower()
    raw = re.sub(r"[^a-z]", "", raw)
    if raw in LAYER_TYPES:
        return raw
    if raw in _TYPE_ALIASES:
        return _TYPE_ALIASES[raw]
    # partial match
    for canonical in LAYER_TYPES:
        if canonical in raw:
            return canonical
    return None


def parse_perception_response(text: str) -> list[LayerNode]:
    """Parse VLM perception output into a flat layer list (sorted by z)."""
    layers: list[LayerNode] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or not line.lower().startswith("z"):
            continue
        m_z = re.search(r"z\s*=\s*(\d+)", line, re.IGNORECASE)
        m_t = re.search(r"type\s*=\s*([a-zA-Z_]+)", line, re.IGNORECASE)
        m_c = re.search(r"count\s*=\s*(\d+)", line, re.IGNORECASE)
        if not (m_z and m_t):
            continue
        z = int(m_z.group(1))
        t = normalize_type(m_t.group(1))
        if not t:
            continue
        c = int(m_c.group(1)) if m_c else 1
        layers.append(LayerNode(z=z, type=t, count=c))
    layers.sort(key=lambda n: n.z)
    return layers


# ─────────────────────────────────────────────────────────────────
# Path 2 — Tree from HTML (parse z-index + class names)
# ─────────────────────────────────────────────────────────────────

# Map common class-name patterns → canonical layer type.
# Order matters: more specific patterns first (e.g. hero-value → value, not hero).
_HTML_CLASS_TO_TYPE = [
    (r"bg-base|bg_base|background", "background"),
    (r"atmos|atmosphere|glow", "atmosphere"),
    (r"decor|decoration|pattern", "decoration"),
    (r"card-value|hero-value|value|metric|percent|stat-num", "value"),
    (r"card-label|hero-subtitle|label|subtitle|tag", "label"),
    (r"card-icon|icon|fa-|emoji|marker|dot|shape", "icon"),
    (r"card-wrap|card-\d|^card$", "card"),
    (r"hero", "hero"),
    (r"panel|container|box|wrap|slide-|^node$|node-", "panel"),
    (r"title|headline|header|heading|step-title|feature-title|card-title", "title"),
    (r"chart|svg|graph", "chart"),
    (r"table|lt-table", "table"),
    (r"arrow", "arrow"),
    (r"connector|connection|bezier|edge", "connector"),
    (r"body|content|description|desc|text|caption|note|detail", "text"),
    (r"line|stroke", "line"),
    (r"badge|chip|pill", "badge"),
]


def _classify_html_element(class_attr: str, inline_style: str) -> str | None:
    """Map an element's class + style to a canonical layer type."""
    blob = f"{class_attr} {inline_style}".lower()
    for pattern, canonical in _HTML_CLASS_TO_TYPE:
        if re.search(pattern, blob):
            return canonical
    return None


_ELEMENT_RE = re.compile(
    r'<div\b[^>]*class\s*=\s*"([^"]*)"[^>]*(?:style\s*=\s*"([^"]*)")?[^>]*>',
    re.IGNORECASE,
)
_Z_INDEX_RE = re.compile(r"z-index\s*:\s*(-?\d+)", re.IGNORECASE)
_STYLE_BLOCK_RE = re.compile(r"<style[^>]*>([\s\S]*?)</style>", re.IGNORECASE)
_CSS_RULE_RE = re.compile(
    r"\.([\w-]+)[^{}]*\{([^{}]*)\}", re.IGNORECASE,
)

# SVG-aware extension: rendered charts use <svg>...<rect/><text/><line/>...</svg>.
# Earlier div-only parser missed these entirely, deflating layer_recall on
# chart-heavy slides (chart sub-elements invisible while perception sees them).
_SVG_BLOCK_RE = re.compile(r"<svg\b[^>]*>([\s\S]*?)</svg>", re.IGNORECASE)
_SVG_OPEN_RE = re.compile(r'<svg\b[^>]*>', re.IGNORECASE)
_SVG_TEXT_RE = re.compile(r"<text\b", re.IGNORECASE)
_SVG_LINE_RE = re.compile(r"<(line|polyline|path)\b", re.IGNORECASE)
_SVG_RECT_RE = re.compile(r"<rect\b", re.IGNORECASE)
_SVG_CIRCLE_RE = re.compile(r"<circle\b", re.IGNORECASE)


def _extract_style_block_z(html: str) -> dict[str, int]:
    """Build {class_name: z_index} from <style> block CSS rules.

    Fixes the inline-only parser bias — single_pass tends to put z-index inside
    `<style>` blocks (e.g., `.card { z-index: 10 }`), and without this lookup
    those z-values were lost (defaulted to z=0), inflating LayerAgent's lead.
    """
    class_z: dict[str, int] = {}
    for sb in _STYLE_BLOCK_RE.findall(html):
        for class_name, body in _CSS_RULE_RE.findall(sb):
            zm = _Z_INDEX_RE.search(body)
            if zm:
                class_z[class_name.lower()] = int(zm.group(1))
    return class_z


def parse_html_tree(html: str) -> list[LayerNode]:
    """Extract layer nodes from rendered HTML, sorted by z-index.

    Reads z-index from BOTH inline `style="..."` and `<style>` block CSS rules,
    preferring inline if both are present (CSS specificity proxy).

    Also walks <svg> blocks: an SVG becomes one `chart` node, its <text>
    descendants contribute `text` nodes, <line>/<polyline>/<path> contribute
    `line`, <circle> contributes `icon`. Without this, SVG-rendered charts
    register as a single panel div and the parser sees zero of the visual
    content the VLM perceives.
    """
    style_block_z = _extract_style_block_z(html)
    by_z_type: dict[tuple[int, str], int] = {}
    for m in _ELEMENT_RE.finditer(html):
        cls = m.group(1) or ""
        style = m.group(2) or ""
        canonical = _classify_html_element(cls, style)
        if not canonical:
            continue
        z_match = _Z_INDEX_RE.search(style)
        if z_match:
            z = int(z_match.group(1))
        else:
            z = 0
            for cn in cls.split():
                if cn.lower() in style_block_z:
                    z = style_block_z[cn.lower()]
                    break
        key = (z, canonical)
        by_z_type[key] = by_z_type.get(key, 0) + 1

    for svg_match in _SVG_BLOCK_RE.finditer(html):
        svg_full = svg_match.group(0)
        svg_open = _SVG_OPEN_RE.match(svg_full).group(0)
        svg_inner = svg_match.group(1)
        # z from the <svg ...> tag's inline style, else mid-band default
        # Default to back band (z<10): perception consistently places chart and
        # its labels at z=1-8, so without inline z-index, classify SVG content
        # as back-band to align bands across reference and generated trees.
        z_match = _Z_INDEX_RE.search(svg_open)
        z = int(z_match.group(1)) if z_match else 5

        by_z_type[(z, "chart")] = by_z_type.get((z, "chart"), 0) + 1
        text_n = len(_SVG_TEXT_RE.findall(svg_inner))
        if text_n:
            by_z_type[(z, "text")] = by_z_type.get((z, "text"), 0) + text_n
        line_n = len(_SVG_LINE_RE.findall(svg_inner))
        if line_n:
            by_z_type[(z, "line")] = by_z_type.get((z, "line"), 0) + line_n
        circle_n = len(_SVG_CIRCLE_RE.findall(svg_inner))
        if circle_n:
            by_z_type[(z, "icon")] = by_z_type.get((z, "icon"), 0) + circle_n
        rect_n = len(_SVG_RECT_RE.findall(svg_inner))
        if rect_n:
            by_z_type[(z, "value")] = by_z_type.get((z, "value"), 0) + rect_n

    layers = [LayerNode(z=z, type=t, count=c)
              for (z, t), c in sorted(by_z_type.items())]
    return layers


# ─────────────────────────────────────────────────────────────────
# LTED — Layer Tree Edit Distance (normalized, 0=identical, 1=disjoint)
# ─────────────────────────────────────────────────────────────────

def lted(tree_a: list[LayerNode], tree_b: list[LayerNode]) -> float:
    """Tree edit distance between two flat layer lists, normalized to [0, 1].

    For minimal version we treat each tree as a multiset of (z_bucket, type)
    pairs. z is bucketed (0-9 = bg, 10-19 = mid, 20+ = front) so different
    numeric encodings still match if they're in the same band. Edit distance
    = symmetric difference size / max-set size.
    """
    def bucket(n: LayerNode) -> tuple[str, str]:
        if n.z < 10: band = "back"
        elif n.z < 20: band = "mid"
        else: band = "front"
        return (band, n.type)

    multi_a: dict[tuple[str, str], int] = {}
    multi_b: dict[tuple[str, str], int] = {}
    for n in tree_a:
        b = bucket(n)
        multi_a[b] = multi_a.get(b, 0) + max(n.count, 1)
    for n in tree_b:
        b = bucket(n)
        multi_b[b] = multi_b.get(b, 0) + max(n.count, 1)

    keys = set(multi_a) | set(multi_b)
    diff = sum(abs(multi_a.get(k, 0) - multi_b.get(k, 0)) for k in keys)
    total = sum(multi_a.values()) + sum(multi_b.values())
    if total == 0:
        return 0.0
    return diff / total


def layer_recall(reference: list[LayerNode], generated: list[LayerNode]) -> float:
    """Recall@type: fraction of reference (band, type) pairs present in generated."""
    def bucket(n: LayerNode) -> tuple[str, str]:
        if n.z < 10: band = "back"
        elif n.z < 20: band = "mid"
        else: band = "front"
        return (band, n.type)

    ref_set = {bucket(n) for n in reference}
    gen_set = {bucket(n) for n in generated}
    if not ref_set:
        return 1.0
    return len(ref_set & gen_set) / len(ref_set)
