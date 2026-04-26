"""Run LayerAgent on the 3 consulting-style seed images to evaluate fidelity.

This is a stress test — consulting decks (Mekko / 2x2 matrix / Harvey-ball
table) are layout patterns our pipeline has never been tested on.
"""
from __future__ import annotations

from pathlib import Path

from layeragent import LayerAgent


_ROOT = Path(__file__).resolve().parents[1]
_SEEDS_DIR = _ROOT / "data" / "eval_dataset" / "seeds_test"


CASES = [
    {
        "image": _SEEDS_DIR / "seed_01_mekko_mckinsey.png",
        "slide_id": "consult_mekko",
        "message": (
            "McKinsey 스타일 Mekko (Marimekko) 차트 슬라이드. "
            "Action title: 'APAC retail drove 67% of FY2025 revenue growth, "
            "led by China and India'. "
            "Subtitle: 'Revenue contribution by region × product category'. "
            "데이터: 4개 region (APAC 45%, NAM 28%, EMEA 18%, LATAM 9%) × "
            "3 product category (Apparel, Electronics, Home). "
            "각 cell 값: APAC Apparel $35.2B, APAC Electronics $28.8B, APAC Home $12.4B, "
            "NAM Apparel $18.1B, NAM Electronics $14.3B, NAM Home $5.9B, "
            "EMEA Apparel $9.7B, EMEA Electronics $6.5B, EMEA Home $3.1B, "
            "LATAM Apparel $4.2B, LATAM Electronics $2.8B, LATAM Home $1.5B. "
            "APAC region 만 강조 (deep navy #003B71), 나머지는 gray tones. "
            "Footer: 'Source: Internal financial data, FY2025'. "
            "Typography: Georgia serif title, Arial sans-serif body."
        ),
    },
    {
        "image": _SEEDS_DIR / "seed_02_matrix_bcg.png",
        "slide_id": "consult_2x2_matrix",
        "message": (
            "BCG 2×2 matrix 슬라이드 (Growth-Share Matrix). "
            "Action title: 'Three product lines are in the Stars quadrant, "
            "justifying 70% of capex'. "
            "X-axis: Market Share (Low → High). Y-axis: Market Growth Rate (Low → High). "
            "4 quadrants: Question Marks (top-left), Stars (top-right), "
            "Dogs (bottom-left), Cash Cows (bottom-right). "
            "Products: ProdA, ProdB, ProdC in Stars (BCG green #00A651, ProdA largest with glow). "
            "ProdD, ProdE in Cash Cows (lighter green). "
            "ProdF, ProdG in Question Marks (gray). ProdH in Dogs (light gray). "
            "Footer: 'Source: Strategic review, Q4 2025'. "
            "Background white, BCG green accent, sans-serif typography."
        ),
    },
    {
        "image": _SEEDS_DIR / "seed_03_table_bain.png",
        "slide_id": "consult_harvey_table",
        "message": (
            "Bain 스타일 비교 표를 만들어. "
            "Action title: 'Vendor B leads on 4 of 5 evaluation criteria, "
            "justifying selection'. "
            "헤더: 평가 기준, Vendor A, Vendor B, Vendor C. "
            "5개 평가 기준 행: "
            "1) Total Cost of Ownership: Vendor A '50% Harvey ball, 경쟁력 있으나 B보다 비쌈', "
            "Vendor B '100% filled, $2.4M lower 5yr TCO', "
            "Vendor C '25% filled, 매우 비쌈'. "
            "2) Implementation speed: A '75%, Q4 2025 출시 가능', "
            "B '100%, Q1 2026 launch 확정', C '50%, Q2 2026 지연 가능'. "
            "3) Feature completeness: A '50%, 핵심 분석 모듈 누락', "
            "B '75%, 90% core features 충족', C '25%, 기본 기능만'. "
            "4) Vendor stability: A '100%, 10년+ 시장 안정', "
            "B '75%, 견고 재무 + 시장 점유 성장', C '50%, 최근 구조조정'. "
            "5) Customer references: A '50%, 혼재된 피드백', "
            "B '100%, 매우 긍정적', C '75%, 니치 시장에서 좋음'. "
            "Vendor B 컬럼을 Bain red (#CC0033) 로 강조. "
            "표 아래 추천 문구: 'Recommendation: proceed with Vendor B for Q1 2026 procurement'. "
            "Footer: 'Source: Vendor RFP scoring, Dec 2025'."
        ),
    },
]


def main() -> None:
    agent = LayerAgent(model="gpt-4o")
    print(f"[test] running LayerAgent on {len(CASES)} consulting-style seeds\n")

    for case in CASES:
        print(f"[test] {case['slide_id']} (image={case['image'].name})")
        out_path = agent.run_from_chat_and_save(
            image_path=case["image"],
            user_message=case["message"],
            slide_id=case["slide_id"],
        )
        print(f"  → {out_path}\n")

    print("[test] done. open results:")
    for case in CASES:
        sid = case["slide_id"]
        print(f"  open results/raw/layeragent-chat/{sid}_seed0.html")


if __name__ == "__main__":
    main()
