"""Render the three HTML variants and capture screenshots for comparison."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright


OUT_DIR = Path("results/vlm_chart_test")


def clean_html(raw: str) -> str:
    """Strip ```html fences and outer wrap if VLM nested a full document."""
    txt = raw

    # Remove ```html ... ``` fences if present
    txt = re.sub(r"```html\s*", "", txt)
    txt = re.sub(r"```\s*$", "", txt)
    txt = re.sub(r"```\s*\n", "", txt)

    # If output contains a nested <!DOCTYPE html>, extract the inner document
    matches = list(re.finditer(r"<!DOCTYPE html>", txt, flags=re.IGNORECASE))
    if len(matches) >= 2:
        # take from the LAST <!DOCTYPE html> onward (the inner one)
        txt = txt[matches[-1].start():]
        # find closing </html>
        end = txt.lower().rfind("</html>")
        if end >= 0:
            txt = txt[: end + len("</html>")]

    return txt.strip()


def render_one(html_path: Path, png_path: Path) -> None:
    raw = html_path.read_text()
    cleaned = clean_html(raw)
    tmp_path = html_path.with_suffix(".clean.html")
    tmp_path.write_text(cleaned)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page = ctx.new_page()
        page.goto(f"file://{tmp_path.resolve()}", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(png_path), clip={"x": 0, "y": 0, "width": 1280, "height": 720})
        browser.close()
    print(f"[render] {html_path.name} → {png_path.name}")


def run():
    for stem in ["A_chart_templates", "B1_vlm_naive", "B2_vlm_chart_aware"]:
        html_path = OUT_DIR / f"{stem}.html"
        png_path = OUT_DIR / f"{stem}.png"
        if html_path.exists():
            render_one(html_path, png_path)

    # Also reference image for side-by-side
    ref = Path("data/eval_dataset/slides/mekko_mckinsey_blue_finance.png")
    if ref.exists():
        (OUT_DIR / "REF_reference.png").write_bytes(ref.read_bytes())
        print(f"[copy] reference → REF_reference.png")


if __name__ == "__main__":
    run()
