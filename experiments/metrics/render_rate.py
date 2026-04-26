"""Render Success Rate — Playwright-based code-validity metric.

A generated HTML "renders successfully" iff:
  1. Playwright loads it without timeout / network failure
  2. The rendered viewport contains at least one visible non-empty element
  3. The slide-container <div> (or fallback root) has non-zero size

Reported metric: fraction of N HTML outputs that pass all three checks.
"""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

from layeragent.utils.common import wrap_slide


_RENDER_PROBE_JS = """
(() => {
  // Collect every element that has measurable visible content.
  const visibles = Array.from(document.querySelectorAll('*'))
    .filter(el => {
      const r = el.getBoundingClientRect();
      const cs = window.getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
      if (parseFloat(cs.opacity) < 0.05) return false;
      if (r.width < 4 || r.height < 4) return false;
      // Has either text or a background or a child with same
      const hasText = (el.innerText || '').trim().length > 0;
      const hasBg = cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)' &&
                    cs.backgroundColor !== 'transparent';
      const hasImage = el.tagName === 'IMG' || cs.backgroundImage !== 'none';
      const hasBorder = parseFloat(cs.borderWidth) > 0;
      return hasText || hasBg || hasImage || hasBorder;
    });
  return {
    n_visible: visibles.length,
    body_h: document.body.scrollHeight,
    body_w: document.body.scrollWidth,
  };
})()
"""


def render_one(html: str, width: int = 1280, height: int = 720) -> dict:
    """Render a single HTML output via Playwright. Returns probe dict."""
    if not html or len(html) < 100:
        return {"rendered": False, "reason": "html too short", "n_visible": 0}

    if "<html" not in html.lower():
        html = wrap_slide(html)

    tmp = Path("/tmp/render_rate_probe.html")
    tmp.write_text(html)

    result = {"rendered": False, "n_visible": 0, "body_w": 0, "body_h": 0}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(viewport={"width": width, "height": height})
            page = ctx.new_page()
            try:
                page.goto(f"file://{tmp.resolve()}", wait_until="networkidle", timeout=10000)
            except Exception:
                page.goto(f"file://{tmp.resolve()}", wait_until="load", timeout=10000)
            page.wait_for_timeout(300)
            try:
                probe = page.evaluate(_RENDER_PROBE_JS)
            except Exception as e:
                browser.close()
                return {"rendered": False, "reason": f"probe failed: {e}", "n_visible": 0}
            browser.close()
        result.update(probe)
        result["rendered"] = (probe["n_visible"] >= 3 and probe["body_w"] > 0)
    except Exception as e:
        result["reason"] = str(e)
    return result


def render_rate(html_paths: list[str | Path]) -> dict:
    """Compute render success rate across N HTML files.

    Returns dict with: rate, n_pass, n_total, per_file (list of probe dicts).
    """
    per_file: list[dict] = []
    for p in html_paths:
        path = Path(p)
        try:
            html = path.read_text()
        except Exception:
            per_file.append({"path": str(path), "rendered": False, "reason": "read failed"})
            continue
        probe = render_one(html)
        probe["path"] = str(path)
        per_file.append(probe)

    n_pass = sum(1 for r in per_file if r.get("rendered"))
    return {
        "rate": n_pass / len(per_file) if per_file else 0.0,
        "n_pass": n_pass,
        "n_total": len(per_file),
        "per_file": per_file,
    }
