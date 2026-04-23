"""exp4 — Model-Agnostic Claim 검증.

본 thesis는 '단일 VLM의 실패가 모델 scale에 불변'이라고 주장한다.
이를 검증하기 위해 single-pass baseline을 GPT-4o, GPT-5.4, Claude-4.6-Opus 세 모델에서 실행 후
ConsistencyScore 및 CCR을 비교한다.

Hypothesis H4:
    ConsistencyScore(single_pass_gpt5.4) < ConsistencyScore(layeragent_full_on_gpt4o)
    AND joint_pass(single_pass_gpt5.4) < joint_pass(layeragent_full_on_gpt4o)
=> 더 강한 모델이어도 consistency/joint fidelity 보장 불가능 → 구조적 문제.

(주의) 이 hypothesis가 기각되면 thesis의 model-agnostic 주장을 약화해야 한다.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=str, default="gpt-4o,gpt-5.4,claude-4.6-opus")
    parser.add_argument("--out", type=str, default="results/raw/exp4_scale_invariance.jsonl")
    args = parser.parse_args()

    models = args.models.split(",")
    out_path = Path(__file__).resolve().parent.parent / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[exp4] single-pass on {models}, compared to LayerAgent-on-GPT-4o")
    print("[exp4] TODO: wire to methods/single_pass.py + metrics/consistency.py + metrics/ccr_cssrich.py")


if __name__ == "__main__":
    main()
