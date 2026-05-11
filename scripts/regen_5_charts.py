"""Regenerate the 5 chart slides with the new chart-type pipelines."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layeragent import LayerAgent
from layeragent.utils.common import save_run

REF_DIR = ROOT / "data" / "eval_dataset" / "slides"
RAW = ROOT / "results" / "raw" / "layeragent_v4"
SHOTS = ROOT / "results" / "screenshots" / "layeragent_v4"

SLIDES = [
    ("line_chart_mckinsey_blue_trend",
     "이 시계열 라인 차트 슬라이드를 정확히 재현해줘. 모든 데이터 포인트, x/y축 라벨, 콜아웃 주석을 보존."),
    ("waterfall_mckinsey_blue_finance",
     "이 waterfall 차트를 정확히 재현해줘. start/positive/negative/total 막대 종류와 누적값 흐름 보존."),
    ("matrix_2x2_mckinsey_blue_risk",
     "이 2x2 매트릭스 슬라이드를 정확히 재현해줘. 모든 사분면의 항목, 축 라벨(Impact/Likelihood), 강조 사분면 보존."),
    ("mekko_mckinsey_blue_finance",
     "이 mekko/marimekko 차트를 정확히 재현해줘. 각 컬럼의 width 비율, 내부 segment 라벨과 값, footer percent 보존."),
    ("harvey_table_mckinsey_blue_options",
     "이 옵션 평가 표(Harvey balls)를 정확히 재현해줘. 행=criteria(weight%), 열=options. 각 셀의 ball fill 정도(0/25/50/75/100%)와 텍스트 보존."),
]


def render(html: Path, png: Path) -> None:
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
        png.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": 1280, "height": 720})
        b.close()


def main():
    agent = LayerAgent(model="gpt-4o")
    for sid, msg in SLIDES:
        old_html = RAW / f"{sid}_seed0.html"
        if old_html.exists():
            old_html.unlink()
        t0 = time.time()
        try:
            html, spec = agent.run_from_chat(
                image_path=str(REF_DIR / f"{sid}.png"),
                user_message=msg,
                slide_id=sid,
            )
            print(f"  parsed slide_type for {sid}: {spec.get('slide_type')} | content keys: {list(spec.get('content',{}).keys())}")
            p = save_run("layeragent_v4", sid, 0, html)
            png = SHOTS / f"{sid}.png"
            render(p, png)
            print(f"  ✓ {sid}  ({time.time()-t0:.1f}s) → {png}")
        except Exception as e:
            print(f"  ✗ {sid}  {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
