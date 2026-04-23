#!/usr/bin/env python3
"""CropLayerAgent 전체 실험: 10개 디자인 + 평가."""

import json, re, sys, time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

DATA_DIR = Path(__file__).parent / "data" / "experiment_designs"
RESULTS_DIR = Path(__file__).parent / "results" / "crop_agent"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

with open(DATA_DIR / "meta.json") as f:
    meta = json.load(f)

style = meta["style"]

print("=" * 70)
print(f"CropLayerAgent Experiment: {len(meta['slides'])} designs")
print("=" * 70)

all_results = {}

for si, sc in enumerate(meta["slides"]):
    sid = sc["id"]
    stype = sc["type"]
    content = sc["content"]
    img_path = DATA_DIR / f"{sid}.png"

    if not img_path.exists():
        continue

    slide_dir = RESULTS_DIR / sid
    slide_dir.mkdir(exist_ok=True)

    # 캐시 확인
    if (slide_dir / "results.json").exists():
        print(f"[{si+1}/10] {sid} — cached")
        with open(slide_dir / "results.json") as f:
            all_results[sid] = json.load(f)
        continue

    print(f"\n[{si+1}/10] {sid} ({stype})...", end=" ", flush=True)

    # Pipeline 리셋 (각 슬라이드마다)
    import src.methods.crop_layer_agent as cla
    cla._pipeline = None
    from src.methods.crop_layer_agent import generate_from_saved_image

    t0 = time.time()
    try:
        result = generate_from_saved_image(str(img_path), sid, stype, content, style)
        html = result["assembled"]
        dt = round(time.time() - t0, 1)
        print(f"{len(html)} chars ({dt:.0f}s)", end=" ", flush=True)
    except Exception as e:
        html = ""
        dt = 0
        print(f"ERROR: {str(e)[:60]}", end=" ", flush=True)

    # 저장
    wrap = f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;display:flex;justify-content:center;align-items:center;min-height:100vh;}}</style>
</head><body><div style="width:1280px;height:720px;overflow:hidden;position:relative;">{html}</div></body></html>"""
    (slide_dir / "F.html").write_text(wrap)

    # 스크린샷
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1280, "height": 720})
            pg.goto(f"file://{slide_dir / 'F.html'}")
            pg.wait_for_timeout(1500)
            pg.screenshot(path=str(slide_dir / "F.png"))
            b.close()
    except:
        pass

    # 평가
    from src.metrics.content_completeness import content_completeness_rate
    from src.metrics.css_effect_preservation import css_richness

    if html:
        ccr = content_completeness_rate(content, html)
        cr = css_richness(html)
        eval_data = {
            "CCR": ccr["rate"],
            "CSS": cr["total_effects"],
            "Colors": cr["unique_colors"],
            "time": dt,
            "chars": len(html),
        }
    else:
        eval_data = {"CCR": 0, "CSS": 0, "Colors": 0, "time": 0, "chars": 0}

    all_results[sid] = eval_data
    (slide_dir / "results.json").write_text(json.dumps(eval_data, indent=2))
    print(f"| CCR={eval_data['CCR']:.2f} CSS={eval_data['CSS']} Colors={eval_data['Colors']}")

# 요약
print(f"\n{'═'*70}")
print("요약")
print(f"{'═'*70}")
print(f"{'Design':<30} {'CCR':>5} {'CSS':>5} {'Colors':>7} {'Time':>6}")
print("-" * 58)

ccr_sum = css_sum = colors_sum = 0
n = 0
for sid, r in all_results.items():
    print(f"{sid:<30} {r['CCR']:>5.2f} {r['CSS']:>5} {r['Colors']:>7} {r['time']:>5.0f}s")
    ccr_sum += r["CCR"]
    css_sum += r["CSS"]
    colors_sum += r["Colors"]
    n += 1

if n > 0:
    print("-" * 58)
    print(f"{'평균':<30} {ccr_sum/n:>5.2f} {css_sum/n:>5.1f} {colors_sum/n:>7.1f}")

# 비교
print(f"\n비교 (GPT-4o):")
print(f"  Baseline A:      CCR=0.80  CSS=2.8   Colors=6.9")
print(f"  LayerAgent F:    CCR=0.85  CSS=13.3  Colors=20.3")
print(f"  CropLayerAgent:  CCR={ccr_sum/n:.2f}  CSS={css_sum/n:.1f}  Colors={colors_sum/n:.1f}")
print(f"  GPT-5.4 A:       CCR=1.00  CSS=46.8  Colors=75.2")

(RESULTS_DIR / "all_results.json").write_text(json.dumps(all_results, indent=2, ensure_ascii=False))
print(f"\nSaved: {RESULTS_DIR}")
