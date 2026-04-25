"""Chat-mode demo for LayerAgent.

Run:
    python -m experiments.demo_chat
    python -m experiments.demo_chat --image data/experiment_designs/design_02_dashboard.png \\
                                    --message "Q4 매출 대시보드. 매출 128억 +23%, 사용자 240만 +15%."

Output: results/raw/layeragent-chat/<slide_id>_seed0.html  (+ .meta.json)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from layeragent import LayerAgent


_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_IMAGE = _ROOT / "data" / "experiment_designs" / "design_02_dashboard.png"
_DEFAULT_MESSAGE = (
    "Q4 2025 비즈니스 성과 대시보드. "
    "매출 128억(+23% YoY), 활성 사용자 240만(+15% MoM), "
    "고객 만족도 4.7/5.0(+0.3). 다크 테마, 글래스모피즘, 차트 영역 포함."
)


def main() -> None:
    p = argparse.ArgumentParser(description="LayerAgent chat-mode demo.")
    p.add_argument("--image", default=str(_DEFAULT_IMAGE),
                   help="참조 디자인 이미지 경로 (PNG/JPG).")
    p.add_argument("--message", default=_DEFAULT_MESSAGE,
                   help="슬라이드 자연어 브리프.")
    p.add_argument("--slide-id", default="chat_demo",
                   help="저장 파일명에 쓰일 라벨.")
    p.add_argument("--model", default="gpt-4o")
    args = p.parse_args()

    print(f"[demo] image    = {args.image}")
    print(f"[demo] message  = {args.message[:80]}{'…' if len(args.message) > 80 else ''}")
    print(f"[demo] model    = {args.model}\n")

    agent = LayerAgent(model=args.model)
    out_path = agent.run_from_chat_and_save(
        image_path=args.image,
        user_message=args.message,
        slide_id=args.slide_id,
    )
    meta_path = out_path.with_suffix(".meta.json")
    print(f"[demo] HTML     → {out_path}")
    if meta_path.exists():
        spec = json.loads(meta_path.read_text())["parsed_spec"]
        print(f"[demo] type     = {spec.get('slide_type')}")
        print(f"[demo] keys     = {list(spec.get('content', {}).keys())}")


if __name__ == "__main__":
    main()
