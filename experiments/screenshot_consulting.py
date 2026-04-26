"""Render the 3 consulting-style LayerAgent outputs to PNG via Playwright."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


_ROOT = Path(__file__).resolve().parents[1]
_HTML_DIR = _ROOT / "results" / "raw" / "layeragent-chat"
_OUT_DIR = _ROOT / "results" / "screenshots" / "consulting_test"
_OUT_DIR.mkdir(parents=True, exist_ok=True)

SLIDES = ["consult_mekko", "consult_2x2_matrix", "consult_harvey_table"]


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=2)
        page = ctx.new_page()
        for sid in SLIDES:
            html_path = _HTML_DIR / f"{sid}_seed0.html"
            out_path = _OUT_DIR / f"{sid}.png"
            page.goto(f"file://{html_path.resolve()}", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(500)
            page.screenshot(path=str(out_path), clip={"x": 0, "y": 0, "width": 1280, "height": 720})
            print(f"  {sid} → {out_path}")
        browser.close()


if __name__ == "__main__":
    main()
