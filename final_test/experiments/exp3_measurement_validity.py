"""exp3 — RQ3 Measurement Validity (KILLER EXPERIMENT).

30 pairs × 8 metrics × 3 VLM judges (Claude, GPT, Gemini) τ-heatmap.

Metrics compared:
- CSS Richness
- CCR
- Block-Match
- element-IoU
- CLIP similarity
- SSIM
- VLM-judge × {Claude-4.6-Opus, GPT-5.4, Gemini-2.5}

Protocol (2026 best practice):
- Tool-grounded (DOM JSON + screenshot)
- Position-randomized
- Swap-debiased
- Cross-model triangulation

Hypothesis H3:
    Kendall τ(structural metrics, VLM-judges) < 0.3
    AND Kendall τ(VLM_i, VLM_j) > 0.6 (post-debias)
=> 양적 메트릭은 perceived visual fidelity를 underdetermine.

Output: results/figures/tau_heatmap.png (paper의 headline figure)
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_pairs", type=int, default=30)
    parser.add_argument("--judges", type=str, default="claude,gpt4o,gemini")
    parser.add_argument("--out", type=str, default="results/raw/exp3_measurement_validity.jsonl")
    args = parser.parse_args()

    out_path = Path(__file__).resolve().parent.parent / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    judges = args.judges.split(",")
    print(f"[exp3] {args.n_pairs} pairs × {len(judges)} judges × tool-grounded + debias")
    print("[exp3] TODO: wire to metrics/vlm_judge.py::ToolGroundedJudge")
    # TODO:
    # 1. load 30 pairs (baseline vs LayerAgent generations)
    # 2. for each pair: compute all 8 metrics (inc. VLM judges with debias)
    # 3. Kendall τ matrix between all metrics
    # 4. plot heatmap; save figure


if __name__ == "__main__":
    main()
