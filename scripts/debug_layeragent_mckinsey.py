"""Run LayerAgent on the McKinsey 5-phase transformation reference image with
per-layer debug snapshots. Each pipeline node dumps its output to
results/debug/<run_name>/ for visual inspection.

Open files in browser order to walk the pipeline:
  01a_analyzer.json / 01b_analyzer_overlay.png
  02_design_director.json
  03_base_bg.html → 04_atmosphere.html → 05_decoration.html
  06_card_idx{N}_solo.html, 06_card_positioned.html
  07_hero_*.html (none expected for this slide)
  08_icons.json
  09_chart.html, 10_table.html (none expected)
  11_assembled_raw.html → 12_style_normalized.html
  13_text_inserted.html → 14_overflow_repaired.html → 99_final.html
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layeragent import LayerAgent  # noqa: E402
IMAGE = ROOT / "data" / "eval_dataset" / "slides" / "process_flow_mckinsey_blue_transformation.png"
import os
RUN_NAME = os.environ.get("RUN_NAME", "mckinsey_blue_transformation")
DEBUG_DIR = ROOT / "results" / "debug" / RUN_NAME

USER_MESSAGE = (
    "5단계 디지털 트랜스포메이션 로드맵 슬라이드. "
    "제목: 'Five-phase transformation roadmap delivers value in 18 months'. "
    "부제: 'Digital transformation phases, Q1 2026 - Q2 2027'. "
    "5개 단계(화살표/chevron 형태로 좌→우 진행):\n"
    "1) Diagnose (Q1 2026) — Assess current state, processes & systems / "
    "Identify value pools & pain points / Define target operating model\n"
    "2) Design (Q2 2026) — Develop future state blueprints / "
    "Prioritize initiatives & build business cases / Design technology architecture\n"
    "3) Pilot (Q3 2026) — Launch MVP in select areas / Test new processes & tools / "
    "Gather user feedback & iterate\n"
    "4) Scale (Q4 2026 - Q1 2027) — Roll out solutions across the organization / "
    "Conduct widespread training & change management / Monitor performance & adjust\n"
    "5) Sustain (Q2 2027 & beyond) — Embed new ways of working / "
    "Establish continuous improvement loops / Measure and realize benefits\n"
    "스타일: McKinsey blue (짙은 네이비 헤더 #1F3864 + 흰 배경). "
    "각 단계는 상단 다크 블루 헤더, 흰 본문(불릿), 하단 분기 라벨 구조."
)


def main():
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[debug] dump dir: {DEBUG_DIR}")
    print(f"[debug] reference image: {IMAGE}")

    agent = LayerAgent(model="gpt-4o")
    out_path = agent.run_from_chat_and_save(
        image_path=str(IMAGE),
        user_message=USER_MESSAGE,
        slide_id="mckinsey_blue_transformation",
        method_name="layeragent-debug-mckinsey",
        debug_dir=str(DEBUG_DIR),
    )
    print(f"[done] final HTML: {out_path}")
    print(f"[done] inspect intermediates: {DEBUG_DIR}")


if __name__ == "__main__":
    main()
