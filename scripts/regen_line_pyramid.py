"""Regenerate 5 line_chart + 5 pyramid slides with new types (multi-series + tree_diagram)."""
from __future__ import annotations

import sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REF_DIR = ROOT / "data" / "eval_dataset" / "slides"
RAW = ROOT / "results" / "raw" / "layeragent_v4"
SHOTS = ROOT / "results" / "screenshots" / "layeragent_v4"

SLIDES = sorted([p.stem for p in REF_DIR.glob("line_chart_*.png")]
                + [p.stem for p in REF_DIR.glob("pyramid_*.png")])

MSG = (
    "이 슬라이드 디자인을 정확히 재현해줘. 모든 텍스트와 시각 구조 보존. "
    "여러 색의 라인이 있으면 multi-series 로, "
    "1개 root + N branches + M leaves 트리 형태면 tree_diagram 으로 분류."
)


def gen_one(sid: str) -> dict:
    from layeragent import LayerAgent
    from layeragent.utils.common import save_run
    t0 = time.time()
    try:
        agent = LayerAgent(model="gpt-4o")
        html, spec = agent.run_from_chat(
            image_path=str(REF_DIR / f"{sid}.png"),
            user_message=MSG,
            slide_id=sid,
        )
        save_run("layeragent_v4", sid, 0, html)
        return {"sid": sid, "status": "ok",
                "type": spec.get("slide_type"),
                "elapsed": round(time.time() - t0, 1)}
    except Exception as e:
        return {"sid": sid, "status": "fail", "err": f"{type(e).__name__}: {e}"}


def render(html: Path, png: Path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page = ctx.new_page()
        try:
            page.goto(f"file://{html.resolve()}", wait_until="networkidle", timeout=15000)
        except Exception:
            page.goto(f"file://{html.resolve()}", wait_until="load", timeout=15000)
        page.wait_for_timeout(200)
        page.screenshot(path=str(png), clip={"x":0,"y":0,"width":1280,"height":720})
        b.close()


def main():
    print(f"[gen] {len(SLIDES)} slides in parallel")
    with ThreadPoolExecutor(max_workers=10) as ex:
        for fut in as_completed({ex.submit(gen_one, s): s for s in SLIDES}):
            r = fut.result()
            print(f"  {r['sid']:<55} {r.get('type','?'):<22} {r['status']} ({r.get('elapsed','?')}s)")

    # Render PNGs sequentially
    from playwright.sync_api import sync_playwright
    print("[render] PNGs ...")
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width":1280,"height":720}, device_scale_factor=1)
        page = ctx.new_page()
        for sid in SLIDES:
            h = RAW / f"{sid}_seed0.html"
            png = SHOTS / f"{sid}.png"
            if not h.exists(): continue
            try:
                page.goto(f"file://{h.resolve()}", wait_until="networkidle", timeout=15000)
            except Exception:
                page.goto(f"file://{h.resolve()}", wait_until="load", timeout=15000)
            page.wait_for_timeout(150)
            page.screenshot(path=str(png), clip={"x":0,"y":0,"width":1280,"height":720})
            print(f"  → {sid}.png")
        b.close()


if __name__ == "__main__":
    main()
