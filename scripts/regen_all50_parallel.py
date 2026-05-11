"""Regenerate all 50 eval_dataset slides via LayerAgent v4 in parallel batches.

Pipeline:
  Phase 1 (parallel, 10 workers per batch × 5 batches): generate HTML
  Phase 2 (sequential): render PNG via single Playwright session

Idempotent: skips slides whose HTML already exists. Failures logged to a
separate JSON so the run can be retried just on failures.
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
RAW = ROOT / "results" / "raw" / "layeragent_v4"
SHOTS = ROOT / "results" / "screenshots" / "layeragent_v4"
LOG_DIR = ROOT / "results" / "eval50_v4_logs"
RAW.mkdir(parents=True, exist_ok=True)
SHOTS.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Generic message — chat_parser auto-detects slide_type from image (now 18 types)
GENERIC_MSG = (
    "이 슬라이드 디자인을 정확히 재현해줘. 모든 텍스트 콘텐츠 (제목, 부제, 라벨, 수치, "
    "축, 범례, 출처) 와 시각 구조 (차트 형태, 색 구분, 강조 영역) 를 빠짐없이 보존."
)

BATCH_SIZE = 10
N_BATCHES = 5


def list_slides() -> list[str]:
    return sorted(p.stem for p in REF_DIR.glob("*.png"))


def gen_one(slide_id: str) -> dict:
    """Generate HTML for one slide. Returns {slide_id, status, slide_type, error?, elapsed}."""
    out = RAW / f"{slide_id}_seed0.html"
    t0 = time.time()
    if out.exists():
        return {"slide_id": slide_id, "status": "skip", "elapsed": 0.0}
    try:
        # Heavy imports inside worker so each thread has its own state
        from layeragent import LayerAgent
        from layeragent.utils.common import save_run
        agent = LayerAgent(model="gpt-4o")
        html, spec = agent.run_from_chat(
            image_path=str(REF_DIR / f"{slide_id}.png"),
            user_message=GENERIC_MSG,
            slide_id=slide_id,
        )
        save_run("layeragent_v4", slide_id, 0, html)
        return {
            "slide_id": slide_id, "status": "ok",
            "slide_type": spec.get("slide_type"),
            "content_keys": list((spec.get("content") or {}).keys()),
            "elapsed": round(time.time() - t0, 1),
        }
    except Exception as e:
        return {
            "slide_id": slide_id, "status": "fail",
            "error": f"{type(e).__name__}: {e}",
            "trace": traceback.format_exc()[-2000:],
            "elapsed": round(time.time() - t0, 1),
        }


def run_phase1():
    """Parallel HTML generation in 5 batches of 10."""
    all_slides = list_slides()
    print(f"[phase1] total={len(all_slides)}, batch_size={BATCH_SIZE}, batches={N_BATCHES}")
    results: list[dict] = []
    for bi in range(N_BATCHES):
        batch = all_slides[bi * BATCH_SIZE:(bi + 1) * BATCH_SIZE]
        if not batch:
            break
        print(f"\n[batch {bi+1}/{N_BATCHES}] slides: {batch}")
        t_batch = time.time()
        with ThreadPoolExecutor(max_workers=BATCH_SIZE) as ex:
            futs = {ex.submit(gen_one, sid): sid for sid in batch}
            for fut in as_completed(futs):
                r = fut.result()
                sid = r["slide_id"]
                if r["status"] == "ok":
                    print(f"  ✓ {sid:<55} {r.get('slide_type','?'):<25} ({r['elapsed']:.0f}s)")
                elif r["status"] == "skip":
                    print(f"  ~ skip {sid}")
                else:
                    print(f"  ✗ {sid:<55} {r.get('error','')}")
                results.append(r)
        print(f"[batch {bi+1}] done in {time.time()-t_batch:.0f}s")

    # Persist results
    log = LOG_DIR / "phase1_results.json"
    log.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    n_ok = sum(1 for r in results if r["status"] == "ok")
    n_skip = sum(1 for r in results if r["status"] == "skip")
    n_fail = sum(1 for r in results if r["status"] == "fail")
    print(f"\n[phase1] ok={n_ok} skip={n_skip} fail={n_fail}  → log {log}")
    return results


def run_phase2():
    """Sequential PNG rendering via single Playwright session."""
    from playwright.sync_api import sync_playwright

    htmls = sorted(RAW.glob("*_seed0.html"))
    print(f"\n[phase2] rendering {len(htmls)} PNGs ...")
    rendered = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page = ctx.new_page()
        for h in htmls:
            sid = h.stem.replace("_seed0", "")
            png = SHOTS / f"{sid}.png"
            if png.exists() and png.stat().st_mtime > h.stat().st_mtime:
                continue
            try:
                page.goto(f"file://{h.resolve()}", wait_until="networkidle", timeout=15000)
            except Exception:
                page.goto(f"file://{h.resolve()}", wait_until="load", timeout=15000)
            page.wait_for_timeout(150)
            page.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": 1280, "height": 720})
            rendered.append(sid)
            if len(rendered) % 5 == 0:
                print(f"  rendered {len(rendered)}/{len(htmls)}")
        b.close()
    print(f"[phase2] done — {len(rendered)} new PNGs (others up-to-date)")


def main():
    t0 = time.time()
    run_phase1()
    run_phase2()
    print(f"\n[total] {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
