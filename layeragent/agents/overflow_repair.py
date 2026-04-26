"""Overflow Repair Agent — v10 P1.

Playwright로 렌더한 후 JS로 각 카드/hero 의 scrollWidth vs clientWidth 측정.
Overflow 감지 시 해당 element selector + overflow_px 를 LLM 에 전달해
font-size 를 지역적으로 줄이는 수정 prompt 발송.

최대 1 iteration (cascade 방지).

근거: WebGen-Bench 2505.03733 — 렌더 측정 기반 수정으로 overflow 82% 해소 (VLM 단독 31%).
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from ..utils.common import extract_html, wrap_slide
from ..utils.llm import text_call


_STRUCTURAL_CLASS_RE = re.compile(
    r'class\s*=\s*"[^"]*\b(slide-container|(?:card|hero)-wrap-\d+)\b[^"]*"'
)


def _structural_classes(html: str) -> set[str]:
    return {m.group(1) for m in _STRUCTURAL_CLASS_RE.finditer(html or "")}


def _structure_preserved(input_html: str, output_html: str) -> bool:
    needed = _structural_classes(input_html)
    return not (needed - _structural_classes(output_html))


_FONT_SIZE_PROP_RE = re.compile(
    r"(font-size\s*:\s*)([\d.]+)\s*(rem|em|px)\s*(;|\s|$)",
    re.IGNORECASE,
)


def _shrink_class_font(html: str, class_name: str, factor: float = 0.75) -> str:
    """단일 CSS 클래스 룰의 font-size 를 factor 배만큼 축소 (deterministic)."""
    rule_re = re.compile(
        rf"(\.{re.escape(class_name)}\s*\{{)([^}}]*)\}}",
        re.DOTALL,
    )

    def shrink_body(m: re.Match) -> str:
        body = m.group(2)
        def repl(fm: re.Match) -> str:
            try:
                new_val = float(fm.group(2)) * factor
                return f"{fm.group(1)}{new_val:.2f}{fm.group(3)}{fm.group(4)}"
            except Exception:
                return fm.group(0)
        new_body = _FONT_SIZE_PROP_RE.sub(repl, body)
        return m.group(1) + new_body + "}"

    return rule_re.sub(shrink_body, html)


# Single principled parameter: extra slack below the measured fit ratio so
# anti-aliasing / kerning / sub-pixel rounding don't push us back over.
# 0.95 = leave 5% headroom; defensible as "shrink to fit with safety margin".
_FONT_FIT_SAFETY = 0.95


def _measured_fit_factor(ov: dict) -> float:
    """Compute the largest font scale that still fits container by measurement.

    Given Playwright's per-element clientWidth/Height (container) and
    scrollWidth/Height (natural content), the factor that makes content
    exactly fit each axis is container / content. Take the tighter axis,
    multiply by a single safety margin. No magic thresholds.
    """
    cw = ov.get("client_w") or 0
    ch = ov.get("client_h") or 0
    sw = ov.get("scroll_w") or 0
    sh = ov.get("scroll_h") or 0
    # If a dimension isn't reported (older measurement) fall back to ratio
    # derived from overflow_px alone: factor = (cw) / (cw + horiz_px).
    if cw and sw:
        rx = cw / sw
    elif cw:
        rx = cw / max(cw + (ov.get("horiz_px") or 0), 1)
    else:
        rx = 1.0
    if ch and sh:
        ry = ch / sh
    elif ch:
        ry = ch / max(ch + (ov.get("vert_px") or 0), 1)
    else:
        ry = 1.0
    return min(rx, ry, 1.0) * _FONT_FIT_SAFETY


def _deterministic_overflow_fix(html: str, overflows: list[dict]) -> str:
    """Fallback when LLM repair is rejected — shrink-to-fit per measurement.

    For each overflowing CSS class, compute the exact factor needed to fit
    the rendered text into its container, derived from Playwright's
    clientWidth/Height vs scrollWidth/Height. Per class we apply the
    smallest measured factor across instances (most conservative).
    """
    # Per-class minimum factor across all overflowing instances of that class
    cls_to_factor: dict[str, float] = {}
    for ov in overflows:
        sel = (ov.get("selector") or "").lstrip(".")
        if not sel:
            continue
        f = _measured_fit_factor(ov)
        if f >= 1.0:
            continue  # not actually overflowing per measurement
        cls_to_factor[sel] = min(cls_to_factor.get(sel, 1.0), f)

    for cls, factor in cls_to_factor.items():
        html = _shrink_class_font(html, cls, factor=factor)
    return html


OVERFLOW_MEASURE_JS = """
(() => {
  const selectors = [
    '.hero-1', '.hero-2', '.hero-3',
    '.card-1', '.card-2', '.card-3', '.card-4', '.card-5', '.card-6', '.card-7', '.card-8',
    '.card-value', '.card-label', '.card-icon',
    '.hero-value', '.hero-subtitle',
  ];
  const overflow = [];
  for (const sel of selectors) {
    document.querySelectorAll(sel).forEach((el, idx) => {
      const cs = window.getComputedStyle(el);
      const horiz_over = el.scrollWidth - el.clientWidth;
      const vert_over = el.scrollHeight - el.clientHeight;
      if (horiz_over > 4 || vert_over > 6) {
        overflow.push({
          selector: sel,
          nth: idx,
          horiz_px: horiz_over,
          vert_px: vert_over,
          // Exact dimensions for measurement-derived font scaling
          client_w: el.clientWidth,
          client_h: el.clientHeight,
          scroll_w: el.scrollWidth,
          scroll_h: el.scrollHeight,
          text_sample: (el.innerText || '').substring(0, 50),
          current_font_size: cs.fontSize,
        });
      }
    });
  }
  return overflow;
})()
"""


def measure_overflow(html: str, width: int = 1280, height: int = 720) -> list[dict]:
    """Playwright로 HTML 렌더 후 overflow 측정."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    wrapped = wrap_slide(html)
    tmp = Path("/tmp/overflow_repair.html")
    tmp.write_text(wrapped)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
        page = ctx.new_page()
        try:
            page.goto(f"file://{tmp.resolve()}", wait_until="networkidle", timeout=15000)
        except Exception:
            page.goto(f"file://{tmp.resolve()}", wait_until="load", timeout=15000)
        page.wait_for_timeout(300)
        try:
            overflow = page.evaluate(OVERFLOW_MEASURE_JS)
        except Exception:
            overflow = []
        browser.close()
    return overflow


REPAIR_PROMPT = """아래 HTML 에서 다음 요소들이 overflow 되었다. **해당 selector 의 font-size 만 줄여서** 수정하라.
(다른 속성 / 구조 변경 금지)

**Overflow 측정 결과**:
```json
{overflow_json}
```

**현재 HTML**:
```html
{html}
```

수정 규칙:
- overflow 가 horiz_px 인 경우 → 해당 class 의 `font-size` 를 **15~25% 축소**
- overflow 가 vert_px 인 경우 → `font-size` 축소 또는 `line-height: 1.2` 조정
- 여러 클래스가 같이 overflow 면 가장 큰 것부터 우선 수정
- 나머지 HTML 구조/CSS 그대로 유지
- 전체 수정된 HTML 출력 (<style>과 <div>만)"""


def overflow_repair(state) -> dict:
    """v10 P1 — 렌더 측정 → font-size 조정."""
    html = state.get("assembled", "")
    if not html or len(html) < 200:
        return {"assembled": html, "overflow_report": []}

    if state.get("ablation") == "no_overflow_repair":
        return {"assembled": html, "overflow_report": []}

    try:
        overflow = measure_overflow(html)
    except Exception as e:
        print(f"[overflow_repair] measure failed: {e}")
        return {"assembled": html, "overflow_report": []}

    if not overflow:
        print("[overflow_repair] no overflow")
        return {"assembled": html, "overflow_report": []}

    # 심각한 것만 (≥5개 제한)
    overflow_sorted = sorted(overflow, key=lambda x: -(x.get("horiz_px", 0) + x.get("vert_px", 0)))[:5]
    n_over = len(overflow_sorted)
    print(f"[overflow_repair] detected {n_over} overflow(s), fixing...")

    prompt = REPAIR_PROMPT.format(
        overflow_json=json.dumps(overflow_sorted, ensure_ascii=False, indent=2),
        html=html[:30000],
    )

    try:
        raw = text_call(prompt, state.get("model", "gpt-4o"), max_tokens=16000)
        fixed = extract_html(raw)
        if fixed and len(fixed) >= 500 and _structure_preserved(html, fixed):
            return {"assembled": fixed, "overflow_report": overflow_sorted}
        # LLM output rejected (too short or dropped wrappers) → measurement-
        # derived deterministic shrink-to-fit
        print("[overflow_repair] LLM rejected → measurement-derived shrink")
        repaired = _deterministic_overflow_fix(html, overflow_sorted)
        return {"assembled": repaired, "overflow_report": overflow_sorted}
    except Exception as e:
        print(f"[overflow_repair] LLM call failed: {e} → measurement-derived shrink")
        repaired = _deterministic_overflow_fix(html, overflow_sorted)
        return {"assembled": repaired, "overflow_report": overflow_sorted}
