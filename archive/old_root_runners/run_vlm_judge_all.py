#!/usr/bin/env python3
"""
VLM-as-Judge를 모든 방법(A/B/C/E/F) × 10개 디자인에 실행.

목적: 양-질 쌍 검증.
  - Method C (H-RAG): Richness=10.3 높으나, VLM-Judge Material/BG/Color는?
  - LayerAgent (F): Richness=26.5 + Material 동반 개선 가설 검증.
"""

import base64
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT.parent / ".env")
sys.path.insert(0, str(ROOT))

from src.metrics.visual_fidelity import vlm_judge

REFERENCE_DIR = ROOT / "data" / "experiment_designs"
RESULTS_DIR = ROOT / "results" / "gpt-4o"
OUT_PATH = ROOT / "results" / "vlm_judge_all.json"

DESIGNS = [
    "design_01_timeline",
    "design_02_dashboard",
    "design_03_comparison_split",
    "design_04_pyramid",
    "design_05_hub_spoke",
    "design_06_before_after",
    "design_07_feature_grid",
    "design_08_roadmap",
    "design_09_layered_stack",
    "design_10_stats_hero",
]

METHODS = ["A", "B", "C", "E", "F"]

METHOD_NAMES = {
    "A": "Baseline",
    "B": "Visual CoT",
    "C": "CoT + H-RAG",
    "E": "Layer Agents (no coord)",
    "F": "LayerAgent (ours)",
}


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def main():
    results = {}
    if OUT_PATH.exists():
        results = json.loads(OUT_PATH.read_text())
        print(f"기존 결과 로드: {sum(len(v) for v in results.values())} 항목")

    total = len(DESIGNS) * len(METHODS)
    done = 0
    failed = []

    for design in DESIGNS:
        ref_path = REFERENCE_DIR / f"{design}.png"
        if not ref_path.exists():
            print(f"[SKIP] {design}: 참조 이미지 없음")
            continue

        ref_b64 = b64(ref_path)
        results.setdefault(design, {})

        for method in METHODS:
            done += 1
            key = f"{design}/{method}"

            if method in results[design]:
                print(f"[{done}/{total}] {key} — 캐시 사용")
                continue

            gen_path = RESULTS_DIR / design / f"{method}.png"
            if not gen_path.exists():
                print(f"[{done}/{total}] {key} — PNG 없음, 스킵")
                failed.append((key, "missing_png"))
                continue

            try:
                t0 = time.time()
                gen_b64 = b64(gen_path)
                scores = vlm_judge(ref_b64, gen_b64, model="claude-4.6-opus")
                dt = time.time() - t0
                results[design][method] = scores
                print(f"[{done}/{total}] {key} ({dt:.1f}s) → L={scores['layout']} M={scores['material']} BG={scores['background']} C={scores['color']} O={scores['overall']}")

                OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"[{done}/{total}] {key} — ERROR: {e}")
                failed.append((key, str(e)))

    print("\n" + "="*60)
    print("완료. 실패 항목:", len(failed))
    for k, e in failed:
        print(f"  - {k}: {e}")

    print("\n" + "="*60)
    print("방법별 평균:")
    print(f"{'Method':<30}{'Layout':>8}{'Material':>10}{'BG':>6}{'Color':>7}{'Overall':>9}")
    for method in METHODS:
        scores_list = [results[d][method] for d in results if method in results[d]]
        if not scores_list:
            continue
        avg = {k: sum(s[k] for s in scores_list) / len(scores_list) for k in ["layout", "material", "background", "color", "overall"]}
        print(f"{method}: {METHOD_NAMES[method]:<25}"
              f"{avg['layout']:>8.2f}{avg['material']:>10.2f}{avg['background']:>6.2f}{avg['color']:>7.2f}{avg['overall']:>9.2f}"
              f"  (n={len(scores_list)})")

    print(f"\n저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
