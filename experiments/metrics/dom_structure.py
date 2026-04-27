"""HTML/DOM-based vocabulary-free metrics.

Measures structural properties of generated HTML directly via Playwright DOM
extraction. Vocabulary-free — uses computed styles + bounding boxes, not class
name regex (the circular flaw of LTED/Layer Recall).

Metrics:
  - VEC  (Visual Element Count):  visible elements with non-trivial styling
  - EDC  (Element Diversity Count): distinct visual style fingerprints
  - VLC  (Visual Layer Count):  distinct effective-z bands among visual elements
  - CRP  (CSS Rich Properties): vocabulary-free CSS richness count
  - HD   (Hierarchy Depth):     max DOM nesting depth among visual elements
  - SC   (Spatial Coverage):    fraction of slide area covered by visual elements
  - ZDX  (explicit z-index distinct count): for diagnostics
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


# JS injected into rendered page to extract structured DOM data.
_EXTRACT_JS = r"""
(() => {
  function bbox(el) {
    const r = el.getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height };
  }
  function isVisible(el) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (parseFloat(cs.opacity) < 0.05) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 10 || r.height < 10) return false;
    if (r.x + r.width < 0 || r.y + r.height < 0) return false;
    if (r.x > 1280 || r.y > 720) return false;
    return true;
  }
  function depth(el) {
    let d = 0;
    while (el.parentElement) { d++; el = el.parentElement; }
    return d;
  }
  function styleFingerprint(cs) {
    return JSON.stringify({
      bg: cs.backgroundColor,
      bgImg: cs.backgroundImage,
      border: cs.borderStyle + '|' + cs.borderColor + '|' + cs.borderWidth,
      radius: cs.borderRadius,
      shadow: cs.boxShadow,
      backdrop: cs.backdropFilter,
      filter: cs.filter,
      opacity: cs.opacity,
    });
  }
  // CSS rich properties — count of "rich" effect uses
  function richProps(cs) {
    let n = 0;
    if (cs.backdropFilter && cs.backdropFilter !== 'none') n++;
    if (cs.filter && cs.filter !== 'none') n++;
    if (cs.boxShadow && cs.boxShadow !== 'none') {
      // Count comma-separated shadow specs
      n += (cs.boxShadow.match(/rgba?\(/g) || []).length;
    }
    if (cs.backgroundImage && cs.backgroundImage !== 'none') {
      // gradient counts
      n += (cs.backgroundImage.match(/gradient/g) || []).length;
    }
    if (parseFloat(cs.opacity) < 1) n++;
    if (cs.borderRadius && cs.borderRadius !== '0px' && cs.borderRadius !== '0%') n++;
    if (cs.transform && cs.transform !== 'none') n++;
    if (cs.mixBlendMode && cs.mixBlendMode !== 'normal') n++;
    return n;
  }

  // Filter: exclude html/body root containers (they trivially overlap everything)
  const all = [...document.querySelectorAll('*')]
    .filter(el => el.tagName.toLowerCase() !== 'html' && el.tagName.toLowerCase() !== 'body')
    .filter(isVisible);

  function hasVisibleStyle(cs) {
    // "Non-trivial styling" = element contributes to visual design
    if (cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)' &&
        cs.backgroundColor !== 'transparent') return true;
    if (cs.backgroundImage && cs.backgroundImage !== 'none') return true;
    if (cs.borderStyle && cs.borderStyle !== 'none' && parseFloat(cs.borderTopWidth) > 0) return true;
    if (cs.boxShadow && cs.boxShadow !== 'none') return true;
    if (cs.backdropFilter && cs.backdropFilter !== 'none') return true;
    if (cs.filter && cs.filter !== 'none') return true;
    return false;
  }

  // Per-element data
  const elements = all.map(el => {
    const cs = getComputedStyle(el);
    const r = bbox(el);
    const z = parseInt(cs.zIndex);
    return {
      tag: el.tagName.toLowerCase(),
      bbox: r,
      area: r.w * r.h,
      depth: depth(el),
      zIndex: cs.zIndex,
      zNum: Number.isFinite(z) ? z : null,
      fingerprint: styleFingerprint(cs),
      rich: richProps(cs),
      hasText: (el.textContent || '').trim().length > 0,
      hasVisualStyle: hasVisibleStyle(cs),
    };
  });

  // *Visual elements* = elements with non-trivial styling (the ones that
  // actually contribute to design — exclude wrapper/spacer divs)
  const visual = elements.filter(e => e.hasVisualStyle);

  // VEC — count of visual elements (non-trivial styling)
  const vec = visual.length;

  // EDC — distinct style fingerprints among VISUAL elements
  const fingerprints = new Set(visual.map(e => e.fingerprint));
  const edc = fingerprints.size;

  // VLC — distinct effective-z bands among VISUAL elements
  // Effective Z: use explicit z-index if set; else bucket by DOM depth
  // (deeper element = on top, since DOM order rules apply)
  function band(e) {
    if (e.zNum !== null) {
      // Bucket explicit z-index into bands of 5 (0-4 -> 0, 5-9 -> 1, ...)
      return 'z:' + Math.floor(e.zNum / 5);
    }
    // No explicit z-index — bucket by DOM depth (proxy for stacking)
    return 'd:' + Math.floor(e.depth / 2);
  }
  const bands = new Set(visual.map(band));
  const vlc = bands.size;

  // CRP — total rich-property uses across visual elements
  const crp = visual.reduce((sum, e) => sum + e.rich, 0);

  // HD — max DOM nesting depth among VISUAL elements
  const hd = visual.length === 0 ? 0 : Math.max(...visual.map(e => e.depth));

  // SC — spatial coverage (union of visual element bboxes / slide area)
  const gridW = 64, gridH = 36, cellW = 1280 / gridW, cellH = 720 / gridH;
  const grid = new Uint8Array(gridW * gridH);
  for (const e of visual) {
    const x0 = Math.max(0, Math.floor(e.bbox.x / cellW));
    const y0 = Math.max(0, Math.floor(e.bbox.y / cellH));
    const x1 = Math.min(gridW, Math.ceil((e.bbox.x + e.bbox.w) / cellW));
    const y1 = Math.min(gridH, Math.ceil((e.bbox.y + e.bbox.h) / cellH));
    for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) grid[y * gridW + x] = 1;
  }
  const filled = grid.reduce((a, b) => a + b, 0);
  const sc = filled / (gridW * gridH);

  // ZDX — distinct explicit z-index values (diagnostic)
  const zVals = new Set(visual.filter(e => e.zNum !== null).map(e => e.zNum));

  return {
    n_total_visible: elements.length,
    vec, edc, vlc, crp, hd, sc,
    zdx: zVals.size,
    z_index_explicit_count: elements.filter(e => e.zNum !== null).length,
    tag_distribution: visual.reduce((acc, e) => {
      acc[e.tag] = (acc[e.tag] || 0) + 1; return acc;
    }, {}),
  };
})()
"""


def extract_dom_metrics(html_path: Path | str, viewport: tuple[int, int] = (1280, 720)) -> dict:
    """Render HTML in Playwright and extract DOM-based metrics."""
    html_path = Path(html_path)
    url = f"file://{html_path.resolve()}"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]},
                                  device_scale_factor=1)
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
        except Exception:
            page.goto(url, wait_until="load", timeout=15000)
        page.wait_for_timeout(500)
        result = page.evaluate(_EXTRACT_JS)
        browser.close()
    return result


def _self_test():
    import sys
    if len(sys.argv) < 2:
        print("usage: python -m experiments.metrics.dom_structure <html_file>")
        return
    res = extract_dom_metrics(sys.argv[1])
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _self_test()
