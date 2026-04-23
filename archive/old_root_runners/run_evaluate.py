#!/usr/bin/env python3
"""
파일럿 결과 평가: 6개 메트릭으로 A/B/C/E/F/F+ 비교.

Primary (reference-free):
  1. CCR - Content Completeness Rate
  2. LOA - Layer Ordering Accuracy
  3. CSS Richness - CSS 효과 속성 절대 수
  4. IIR - Icon Integrity Rate

Secondary (vs design image):
  5. CLIP Score
  6. SSIM
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image

RESULTS_DIR = Path(__file__).parent / "results" / "pilot"
DATA_DIR = Path(__file__).parent / "data" / "design_images"


def load_html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main():
    # 콘텐츠 데이터 로드
    with open(DATA_DIR / "session_meta.json") as f:
        meta = json.load(f)
    content = meta["slide_contents"][2]["content"]  # slide_003

    # 디자인 이미지
    design_img = Image.open(DATA_DIR / "slide_003_design.png")

    methods = ["A", "B", "C", "E", "F", "Fplus"]
    results = {}

    for method in methods:
        html_path = RESULTS_DIR / f"method_{method}.html"
        screenshot_path = RESULTS_DIR / f"method_{method}.png"

        if not html_path.exists():
            print(f"  {method}: HTML 없음, 스킵")
            continue

        html = load_html(html_path)
        print(f"\n{'─'*50}")
        print(f"  Method {method}")
        print(f"{'─'*50}")

        entry = {"method": method}

        # ── 1. CCR ──
        from src.metrics.content_completeness import content_completeness_rate
        ccr = content_completeness_rate(content, html)
        entry["CCR"] = ccr["rate"]
        entry["CCR_high"] = ccr["high_importance_rate"]
        entry["CCR_found"] = f"{ccr['found_items']}/{ccr['total_items']}"
        print(f"  CCR: {ccr['rate']:.2f} (high: {ccr['high_importance_rate']:.2f}, {ccr['found_items']}/{ccr['total_items']} items)")

        # ── 2. LOA ──
        from src.metrics.layer_ordering import layer_ordering_accuracy
        loa = layer_ordering_accuracy(html)
        entry["LOA_z_usage"] = loa["z_index_usage_rate"]
        entry["LOA_z_levels"] = loa["unique_z_levels"]
        entry["LOA_abs_count"] = loa["absolute_count"]
        print(f"  LOA: z-usage={loa['z_index_usage_rate']:.2f}, levels={loa['unique_z_levels']}, abs={loa['absolute_count']}")

        # ── 3. CSS Richness ──
        from src.metrics.css_effect_preservation import css_richness
        cr = css_richness(html)
        entry["CSS_effects"] = cr["total_effects"]
        entry["CSS_colors"] = cr["unique_colors"]
        entry["CSS_detail"] = cr["detail"]
        print(f"  CSS: effects={cr['total_effects']}, colors={cr['unique_colors']}")
        print(f"       {cr['detail']}")

        # ── 4. IIR ──
        from src.metrics.icon_integrity import icon_integrity_rate
        iir = icon_integrity_rate(html)
        entry["IIR"] = iir["rate"]
        entry["IIR_detail"] = f"proper={iir['proper']}, broken={iir['broken']}, empty={iir['empty']}"
        print(f"  IIR: {iir['rate']:.2f} ({iir['proper']}p/{iir['broken']}b/{iir['empty']}e)")

        # ── 5 & 6. CLIP + SSIM ──
        if screenshot_path.exists():
            gen_img = Image.open(screenshot_path)
            from src.metrics.visual_similarity import compute_ssim, compute_clip_score
            ssim = compute_ssim(design_img, gen_img)
            entry["SSIM"] = ssim
            print(f"  SSIM: {ssim:.4f}")

            try:
                clip = compute_clip_score(design_img, gen_img)
                entry["CLIP"] = clip
                print(f"  CLIP: {clip:.4f}")
            except Exception as e:
                entry["CLIP"] = None
                print(f"  CLIP: error ({e})")
        else:
            entry["SSIM"] = None
            entry["CLIP"] = None

        results[method] = entry

    # ── 요약 테이블 ──
    print(f"\n{'='*70}")
    print("요약 (slide_003 three_column)")
    print(f"{'='*70}")
    print(f"{'Method':<8} {'CCR':>6} {'LOA':>6} {'CSS':>5} {'Colors':>7} {'IIR':>5} {'SSIM':>6}")
    print("-" * 52)
    for method in methods:
        if method not in results:
            continue
        r = results[method]
        ccr_val = f"{r['CCR']:.2f}"
        loa_val = f"{r['LOA_z_usage']:.2f}"
        css_val = f"{r['CSS_effects']}"
        colors_val = f"{r['CSS_colors']}"
        iir_val = f"{r['IIR']:.2f}"
        ssim_val = f"{r.get('SSIM', 0):.3f}" if r.get('SSIM') else "N/A"
        print(f"{method:<8} {ccr_val:>6} {loa_val:>6} {css_val:>5} {colors_val:>7} {iir_val:>5} {ssim_val:>6}")

    # JSON 저장
    # detail 등 non-serializable 제거
    for method, r in results.items():
        if "CSS_detail" in r:
            r["CSS_detail"] = str(r["CSS_detail"])

    (RESULTS_DIR / "evaluation.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str)
    )
    print(f"\nSaved: {RESULTS_DIR / 'evaluation.json'}")


if __name__ == "__main__":
    main()
