"""exp2 — RQ2 Content-Style Isolation.

3 conditions × 10 slides × 3 seeds = 90 generations.

Conditions:
- (a) single_pass (GPT-4o, CSS 지식 주입 없음)
- (b) layeragent_no_textinserter  (텍스트를 Card Detail Agent 가 처리)
- (c) layeragent_full              (텍스트는 Text Inserter 가 별도 처리)

Primary: CCR (metrics/ccr_cssrich.py), CSS Richness
Joint-pass rate: CCR >= 0.7 AND CSS Richness >= 10 (DreamHouse style orthogonality)

Hypothesis H2:
    joint_pass(full) - joint_pass(no_textinserter) >= 0.25
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_seeds", type=int, default=3)
    parser.add_argument("--out", type=str, default="results/raw/exp2_content_isolation.jsonl")
    args = parser.parse_args()

    out_path = Path(__file__).resolve().parent.parent / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[exp2] 3 conditions × 10 slides × {args.n_seeds} seeds")
    print("[exp2] TODO: wire to methods/*.py and metrics/ccr_cssrich.py")


if __name__ == "__main__":
    main()
