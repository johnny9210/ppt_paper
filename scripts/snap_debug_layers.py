"""Use Playwright to render each debug HTML to a PNG so I can visually
diagnose layer-by-layer which stage degrades the slide."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import os
RUN_NAME = os.environ.get("RUN_NAME", "mckinsey_blue_transformation")
DEBUG_DIR = ROOT / "results" / "debug" / RUN_NAME
OUT_DIR = DEBUG_DIR / "screenshots"
OUT_DIR.mkdir(exist_ok=True)


def main():
    from playwright.sync_api import sync_playwright

    targets = sorted(DEBUG_DIR.glob("*.html"))
    print(f"[snap] {len(targets)} HTML files")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page = ctx.new_page()
        for f in targets:
            try:
                page.goto(f"file://{f.resolve()}", wait_until="networkidle", timeout=15000)
            except Exception:
                page.goto(f"file://{f.resolve()}", wait_until="load", timeout=15000)
            page.wait_for_timeout(150)
            out = OUT_DIR / (f.stem + ".png")
            page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": 1280, "height": 720}, full_page=False)
            print(f"  → {out.name}")
        browser.close()


if __name__ == "__main__":
    main()
