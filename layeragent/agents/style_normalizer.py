"""Style Normalizer — deterministic CSS unification + scoping across cards/heroes.

Replaces the previous LLM-based rewrite, which proved unfaithful: the model
silently stripped layout wrappers (.slide-container, .card-wrap-N, title divs)
even though the prompt forbade structural changes. Pure regex over .card-N /
.hero-N CSS rule bodies guarantees no structural element is touched.

Two passes
----------
Pass 1 — Scope child selectors to their parent card/hero:
    Each card_detail emits `<style>` blocks containing both `.card-N { ... }`
    (specific) and `.card-value / .card-icon / .card-label { ... }` (global).
    Without scoping, the LAST card's declaration of `.card-value` cascades to
    ALL cards via CSS specificity/order. Pass 1 rewrites each block's child
    selectors to `.card-N .card-value` etc., making the rules locally
    scoped and immune to inter-card cascade collision.

Pass 2 — Harmonize visual properties across `.card-N { ... }` rule bodies:
    For box-shadow / border-radius / border / backdrop-filter / background,
    pick the most common value across cards and rewrite each rule to use it.

What it does NOT touch
----------------------
- HTML structure (no div add/remove/reorder)
- class names, id attributes, inline styles on wrapping divs
- position / left / top / width / height / z-index (layout)
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
    """Pass 2: harmonize visual props across .card-N / .hero-N CSS rule bodies."""
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


# Pass 1 — CSS scoping. Each `<style>` block emitted by card_detail/hero_detail
# typically contains a parent rule (`.card-N { ... }`) and several unscoped
# child rules (`.card-value / .card-icon / .card-label / .hero-value /
# .hero-subtitle { ... }`). Because the cards are appended into a single
# document, the LAST `<style>` defining `.card-value` wins globally and its
# (possibly buggy) values cascade to every card. We rewrite each block so the
# child selectors are scoped to whichever parent class lives in the same
# block, eliminating cross-card cascade collision.

_STYLE_BLOCK_RE = re.compile(r"(<style[^>]*>)([\s\S]*?)(</style>)", re.IGNORECASE)
_PARENT_CLASS_RE = re.compile(r"\.((?:card|hero)-\d+)\s*\{", re.IGNORECASE)
_CHILD_SELECTOR_RE = re.compile(
    # Match each comma-separated selector at the start of a rule that begins
    # with `.card-value`, `.card-icon`, `.card-label`, `.hero-value`,
    # `.hero-subtitle` (i.e., unscoped child selectors).
    r"(^|,|\}|\s)(\s*)"
    r"(\.(?:card-value|card-icon|card-label|hero-value|hero-subtitle)(?:\s*[,>+~]\s*[^\{,]*)?)"
    r"(\s*[,\{])",
    re.IGNORECASE,
)


def _scope_block(block: str) -> str:
    """Prepend `.card-N ` (or `.hero-N`) to unscoped child selectors in this block."""
    parent_match = _PARENT_CLASS_RE.search(block)
    if not parent_match:
        return block
    parent = parent_match.group(1)  # e.g. "card-6"

    # Skip selectors that already contain the parent class (already scoped)
    def repl(m: re.Match) -> str:
        leading, ws, sel, trailing = m.group(1), m.group(2), m.group(3), m.group(4)
        sel_lower = sel.lower().strip()
        if f".{parent.lower()}" in sel_lower:
            return m.group(0)
        return f"{leading}{ws}.{parent} {sel}{trailing}"

    return _CHILD_SELECTOR_RE.sub(repl, block)


def scope_card_child_selectors(html: str) -> str:
    """Scope unscoped `.card-value/.card-icon/.card-label` rules to their parent card.

    Iterates each `<style>` block; if a block contains a `.card-N { ... }` (or
    `.hero-N { ... }`) parent rule, child selectors in the same block are
    rewritten to `.card-N .card-value { ... }` form. Blocks that have no
    parent rule (e.g. global slide-container styles) are left alone.
    """
    if not html:
        return html

    def replace_block(m: re.Match) -> str:
        return m.group(1) + _scope_block(m.group(2)) + m.group(3)

    return _STYLE_BLOCK_RE.sub(replace_block, html)


def style_normalizer(state) -> dict:
    """LangGraph node — deterministic CSS scoping (Pass 1) + harmonization (Pass 2)."""
    html = state.get("assembled_raw", "")
    if not html:
        return {"assembled": ""}
    if state.get("ablation") == "no_style_norm":
        return {"assembled": html}
    html = scope_card_child_selectors(html)
    html = normalize_card_styles(html)
    return {"assembled": html}
