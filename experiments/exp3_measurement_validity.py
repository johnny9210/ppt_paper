"""exp3 — RQ3 Convergent Reliability + Provisional Measurement Validity (KILLER EXPERIMENT).

본 실험은 두 부분으로 구성된다:

A. **메인 실험** — 30 pairs × 8 metrics × 3 VLM judges (Claude, GPT, Gemini) τ-heatmap.
   Metrics compared:
   - CSS Richness, CCR, Block-Match, element-IoU, CLIP, SSIM
   - VLM-judge × {Claude-4.6-Opus, GPT-5.4, Gemini-2.5}

B. **Tool-grounding ablation** (리뷰어 추가 요구) — 같은 30 pair × 3 judge에 대해
   *with-tool-grounding* (DOM JSON + screenshot) vs *no-tool-grounding* (screenshot only)
   를 비교하여 본 슬라이드 도메인에서 tool grounding이 verdict consistency를 끌어올리는지 검증.
   2026 결과(71→89%)의 슬라이드 도메인 재현을 시도한다.

Protocol (2026 best practice):
- Tool-grounded (DOM JSON + screenshot) — 메인 condition
- No-tool-grounded (screenshot only) — ablation condition
- Position-randomized
- Swap-debiased
- Cross-model triangulation

Hypothesis H3:
    H3(a)  Kendall τ(structural metrics, VLM-judges) < 0.3 (양적 underdetermines)
    H3(b)  Kendall τ(VLM_i, VLM_j) > 0.6 post-debias (cross-model 합의)
    H3(c)  agreement(with-tool) > agreement(no-tool) by ≥10 percentage points
           (slide-domain tool-grounding 효과 확인)

(τ thresholds 0.3 / 0.6 는 본 실험 설계 시점에 사전 등록되며, paper 부록에 명시된다.)

Output: results/figures/tau_heatmap.png (paper의 headline figure)
        results/raw/exp3_with_tool.jsonl   — with grounding raw scores
        results/raw/exp3_no_tool.jsonl     — no grounding raw scores
        results/tables/exp3_tau_matrix.csv  — final τ matrix
        results/tables/exp3_grounding_ablation.csv — H3(c) summary
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_pairs", type=int, default=30)
    parser.add_argument("--judges", type=str, default="claude,gpt4o,gemini")
    parser.add_argument("--ablate_grounding", action="store_true",
                        help="Run both with-tool and no-tool conditions for grounding ablation")
    parser.add_argument("--out_dir", type=str, default="results/raw")
    args = parser.parse_args()

    out_dir = Path(__file__).resolve().parent.parent / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    judges = args.judges.split(",")
    print(f"[exp3] {args.n_pairs} pairs × {len(judges)} judges × position-randomize + swap-debias")
    if args.ablate_grounding:
        print("[exp3] tool-grounding ablation: with-tool vs no-tool")
    print(f"[exp3] outputs → {out_dir}")
    # TODO (구현 단계):
    # 1. data/slide_specs.jsonl 에서 10 design × 3 method-pair = 30 pairs 로딩
    # 2. for each pair, judge in judges, condition in (with_tool, no_tool):
    #       result = ToolGroundedJudge(model=judge, tool_grounded=condition).pairwise(...)
    #       jsonl에 append
    # 3. 모든 metric을 계산: CSS Richness, CCR, Block-Match, element-IoU, CLIP, SSIM, VLM-judge x 3
    # 4. Kendall τ 행렬 계산 → heatmap (matplotlib/seaborn)
    # 5. tool-grounding ablation: with-tool vs no-tool agreement % 비교 → CSV로 저장


if __name__ == "__main__":
    main()
