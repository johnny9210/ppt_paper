"""Style Normalizer — deterministic CSS unification across cards/heroes.

Replaces the previous LLM-based rewrite, which proved unfaithful: the model
silently stripped layout wrappers (.slide-container, .card-wrap-N, title divs)
even though the prompt forbade structural changes. Pure regex over .card-N /
.hero-N CSS rule bodies guarantees no structural element is touched.

What it does
------------
Across all `.card-N { ... }` (and `.hero-N { ... }`) rule bodies in the
assembled HTML, picks the most common value for visually-shared properties
(box-shadow, border-radius, border, backdrop-filter, background) and rewrites
each rule to use the canonical value. Rules with fewer than two occurrences
are left alone.

What it does NOT touch
----------------------
- HTML structure (no div add/remove/reorder)
- class names, id attributes, inline styles on wrapping divs
- position / left / top / width / height / z-index (layout)
- Any <style> blocks for non-`.card-N` / non-`.hero-N` selectors
"""
from __future__ import annotations

import re
from collections import Counter


_HARMONIZE_PROPS: tuple[str, ...] = (
    "box-shadow",
    "border-radius",
    "border",
    "backdrop-filter",
    "background",
    "background-color",
)

_RULE_RE = re.compile(
    r"(\.(?:card|hero)-\d+\s*\{)([^}]*)\}",
    re.DOTALL,
)

_PROP_RE = re.compile(r"([\w-]+)\s*:\s*([^;]+?)\s*(?:;|$)", re.DOTALL)


def _parse_props(body: str) -> dict[str, str]:
    return {m.group(1).strip(): m.group(2).strip() for m in _PROP_RE.finditer(body)}


def _canonical_values(rules_props: list[dict[str, str]]) -> dict[str, str]:
    canonical: dict[str, str] = {}
    for prop in _HARMONIZE_PROPS:
        values = [r[prop] for r in rules_props if prop in r]
        if len(values) >= 2:
            canonical[prop] = Counter(values).most_common(1)[0][0]
    return canonical


def _rewrite_body(body: str, canonical: dict[str, str]) -> str:
    out = body
    for prop, val in canonical.items():
        pattern = re.compile(
            rf"({re.escape(prop)}\s*:\s*)[^;]+?(\s*(?:;|$))",
            re.DOTALL,
        )
        out = pattern.sub(lambda m: f"{m.group(1)}{val}{m.group(2)}", out)
    return out


def normalize_card_styles(html: str) -> str:
    """Harmonize visual props across .card-N / .hero-N CSS rule bodies."""
    if not html:
        return html
    matches = list(_RULE_RE.finditer(html))
    if len(matches) < 2:
        return html

    rules_props = [_parse_props(m.group(2)) for m in matches]
    canonical = _canonical_values(rules_props)
    if not canonical:
        return html

    out_parts: list[str] = []
    cursor = 0
    for m in matches:
        out_parts.append(html[cursor:m.start()])
        out_parts.append(m.group(1))
        out_parts.append(_rewrite_body(m.group(2), canonical))
        out_parts.append("}")
        cursor = m.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def style_normalizer(state) -> dict:
    """LangGraph node — deterministic CSS unification, no LLM call."""
    html = state.get("assembled_raw", "")
    if not html:
        return {"assembled": ""}
    if state.get("ablation") == "no_style_norm":
        return {"assembled": html}
    return {"assembled": normalize_card_styles(html)}
