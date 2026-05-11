"""Regenerate D₂ (no_text_inserter) and D₄ (no_designspec) ablation outputs on
LayerAgent v4 (chart_templates enabled). 50 slides × 2 ablations = 100 cells.

Pipeline:
  Phase 1: HTML generation (parallel, 10 workers per batch × 5 batches per ablation)
  Phase 2: PNG render (sequential, Playwright)

Outputs:
  results/raw/layeragent_v4-no_text_inserter/{sid}_seed0.html
  results/raw/layeragent_v4-no_designspec/{sid}_seed0.html
  results/screenshots/layeragent_v4-no_text_inserter/{sid}.png
  results/screenshots/layeragent_v4-no_designspec/{sid}.png
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REF_DIR = ROOT / "data" / "eval_dataset" / "slides"

ABLATIONS = ["no_text_inserter", "no_designspec"]
BATCH_SIZE = 10

GENERIC_MSG = (
    "이 슬라이드 디자인을 정확히 재현해줘. 모든 텍스트 콘텐츠 (제목, 부제, 라벨, 수치, "
    "축, 범례, 출처) 와 시각 구조 (차트 형태, 색 구분, 강조 영역) 를 빠짐없이 보존."
)


def list_slides() -> list[str]:
    return sorted(p.stem for p in REF_DIR.glob("*.png"))


def gen_one(slide_id: str, ablation: str, raw_dir: Path) -> dict:
    out = raw_dir / f"{slide_id}_seed0.html"
    t0 = time.time()
    if out.exists():
        return {"slide_id": slide_id, "ablation": ablation, "status": "skip", "elapsed": 0.0}
    try:
        from layeragent import LayerAgent
        agent = LayerAgent(model="gpt-4o", ablation=ablation)
        html, spec = agent.run_from_chat(
            image_path=str(REF_DIR / f"{slide_id}.png"),
            user_message=GENERIC_MSG,
            slide_id=slide_id,
        )
        out.write_text(html)
        return {
            "slide_id": slide_id, "ablation": ablation, "status": "ok",
            "slide_type": spec.get("slide_type"),
            "elapsed": round(time.time() - t0, 1),
        }
    except Exception as e:
        return {
            "slide_id": slide_id, "ablation": ablation, "status": "fail",
            "error": f"{type(e).__name__}: {e}",
            "trace": traceback.format_exc()[-2000:],
            "elapsed": round(time.time() - t0, 1),
        }


def phase1_generate(ablation: str):
    raw_dir = ROOT / "results" / "raw" / f"layeragent_v4-{ablation}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    slides = list_slides()
    print(f"\n[gen/{ablation}] {len(slides)} slides → {raw_dir}")

    results = []
    for bi in range(0, len(slides), BATCH_SIZE):
        batch = slides[bi:bi + BATCH_SIZE]
        print(f"  [batch {bi//BATCH_SIZE+1}] {len(batch)} slides ...")
        t = time.time()
        with ThreadPoolExecutor(max_workers=BATCH_SIZE) as ex:
            futs = {ex.submit(gen_one, sid, ablation, raw_dir): sid for sid in batch}
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                tag = r["status"]
                marker = "✓" if tag == "ok" else ("○" if tag == "skip" else "✗")
                print(f"    {marker} {r['slide_id']:<55} {r.get('slide_type','?'):<22} {r['elapsed']}s")
        print(f"  batch done in {time.time()-t:.1f}s")

    ok = sum(1 for r in results if r["status"] == "ok")
    sk = sum(1 for r in results if r["status"] == "skip")
    fl = sum(1 for r in results if r["status"] == "fail")
    print(f"[gen/{ablation}] ok={ok} skip={sk} fail={fl}")
    return results


def phase2_render(ablation: str):
    raw_dir = ROOT / "results" / "raw" / f"layeragent_v4-{ablation}"
    shots_dir = ROOT / "results" / "screenshots" / f"layeragent_v4-{ablation}"
    shots_dir.mkdir(parents=True, exist_ok=True)
    slides = list_slides()

    print(f"\n[render/{ablation}] → {shots_dir}")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page = ctx.new_page()
        for sid in slides:
            html = raw_dir / f"{sid}_seed0.html"
            png = shots_dir / f"{sid}.png"
            if not html.exists() or png.exists():
                continue
            try:
                page.goto(f"file://{html.resolve()}", wait_until="networkidle", timeout=15000)
            except Exception:
                page.goto(f"file://{html.resolve()}", wait_until="load", timeout=15000)
            page.wait_for_timeout(150)
            page.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": 1280, "height": 720})
            print(f"  → {sid}.png")
        b.close()


def main():
    t0 = time.time()
    for ab in ABLATIONS:
        phase1_generate(ab)
        phase2_render(ab)
    print(f"\n[ablation regen] total elapsed {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
