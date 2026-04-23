"""Playwright로 HTML 결과를 1280x720 PNG로 렌더링."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def screenshot_files(html_paths: list[Path], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=2)
        page = ctx.new_page()
        for html_path in html_paths:
            url = f"file://{html_path.resolve()}"
            png_path = out_dir / (html_path.stem + ".png")
            try:
                page.goto(url, wait_until="networkidle", timeout=15000)
            except Exception:
                page.goto(url, wait_until="load", timeout=15000)
            # 폰트/이미지 로딩 안정화
            page.wait_for_timeout(500)
            page.screenshot(path=str(png_path), clip={"x": 0, "y": 0, "width": 1280, "height": 720})
            print(f"  ✓ {html_path.name} → {png_path.name}")
        browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", default="A_gpt54", help="condition directory under results/raw/")
    parser.add_argument("--out", default=None, help="output directory (default: results/screenshots/<method>)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    src = root / "results" / "raw" / args.method
    if not src.exists():
        print(f"[err] {src} not found", file=sys.stderr)
        sys.exit(1)

    out = Path(args.out) if args.out else root / "results" / "screenshots" / args.method
    htmls = sorted(src.glob("*.html"))
    print(f"[shot] {len(htmls)} files in {src} → {out}")
    screenshot_files(htmls, out)


if __name__ == "__main__":
    main()
