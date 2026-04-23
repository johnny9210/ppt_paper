"""exp1 — RQ1 Cross-Element Consistency.

3 conditions × 10 slides × 3 seeds = 90 generations.

Conditions:
- (a) single_pass_gpt4o
- (b) layeragent_no_stylenorm  (ablation)
- (c) layeragent_full

Primary metric: ConsistencyScore (metrics/consistency.py)
Stats: paired Wilcoxon (b vs c), effect size (c - a).

Hypothesis H1:
    ConsistencyScore(full) - ConsistencyScore(no_stylenorm) >= 0.15
    AND paired Wilcoxon p < 0.05
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_seeds", type=int, default=3)
    parser.add_argument("--out", type=str, default="results/raw/exp1_consistency.jsonl")
    args = parser.parse_args()

    out_path = Path(__file__).resolve().parent.parent / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[exp1] 3 conditions × 10 slides × {args.n_seeds} seeds")
    print("[exp1] TODO: wire to methods/*.py and metrics/consistency.py")
    print(f"[exp1] results will be written to: {out_path}")
    # TODO:
    # 1. load 10 slide specs from data/slide_specs.jsonl
    # 2. for each (spec, seed) in cross product:
    #    for each condition in (single_pass, no_stylenorm, full):
    #       html = method.run(spec, seed)
    #       score = consistency_score(html)
    #       write to out_path
    # 3. report per-condition mean/std + paired Wilcoxon


if __name__ == "__main__":
    main()
