"""Quick experiment: VLM-only chart rendering vs chart_templates.

Compares two approaches for rendering a mekko chart given a reference image:
  (A) chart_templates: Python f-string SVG generator (current LayerAgent)
  (B) VLM-only: GPT-4o renders the chart HTML/SVG directly from the image,
      with a chart-type-aware prompt (variable-width × stacked segments).
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from layeragent.utils.llm import vision_call
from layeragent.libraries.chart_templates import render_chart_slide


REF_IMG = Path("data/eval_dataset/slides/mekko_mckinsey_blue_finance.png")
OUT_DIR = Path("results/vlm_chart_test")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────
# Prompt (A): naive "convert this to HTML"
# ─────────────────────────────────────────────────────────────────────
PROMPT_NAIVE = """이 슬라이드 이미지를 1280×720 단일 HTML 페이지로 변환하세요.
순수 HTML + CSS 만 사용하세요. JavaScript, <img> 금지.
설명 없이 HTML 코드만 출력하세요."""


# ─────────────────────────────────────────────────────────────────────
# Prompt (B): chart-type-aware, explicit structural instructions
# ─────────────────────────────────────────────────────────────────────
PROMPT_CHART_AWARE = """이 이미지는 **Mekko (Marimekko) 차트**입니다.
정확한 mekko 차트를 SVG로 1280×720 단일 HTML 페이지로 재현하세요.

Mekko 차트의 정의 (반드시 지킬 것):
- 가로로 N개의 column 이 나열되며 각 column 의 **width 는 그 카테고리의 총합 비율** 에 비례한다.
- 각 column 안에는 M개의 stacked segment 가 세로로 쌓이며, 각 segment 의 **height 는 그 column 내 subcategory 비율** 에 비례한다.
- 따라서 전체 직사각형의 면적이 100% 이고, 각 cell 면적이 (column 비율 × segment 비율) 이다.

구현 요구사항:
1. SVG `<rect>` 로 모든 cell 을 직접 그리세요. CSS flexbox 로 막대만 그리는 단순화는 금지.
2. 각 cell 의 x, y, width, height 좌표를 카테고리/세그먼트 비율에 정확히 비례하도록 계산하세요.
3. 각 column 상단에 카테고리 라벨, 각 cell 안 또는 옆에 값 라벨을 표시하세요.
4. McKinsey navy (#001E62) 계열의 색상 팔레트를 사용하세요.
5. 상단에 슬라이드 제목, 하단에 source 라벨도 포함하세요.

이미지를 잘 분석해서 각 column 의 너비 비율, 각 segment 의 높이 비율을 정확히 추출한 뒤 SVG 좌표로 옮기세요.
순수 HTML + SVG 만 사용. JavaScript, `<img>`, external CSS 금지.
설명 없이 HTML 코드만 출력하세요."""


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def wrap_html(body_html: str, title: str) -> str:
    """Wrap raw HTML body in a 1280×720 container if not already."""
    if body_html.lstrip().startswith("<!DOCTYPE") or body_html.lstrip().startswith("<html"):
        return body_html
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{margin:0;background:#1a1a1a;display:flex;justify-content:center;align-items:center;min-height:100vh;}}</style>
</head><body>
<div style="width:1280px;height:720px;overflow:hidden;position:relative;background:#fff;">
{body_html}
</div></body></html>"""


def run():
    if not REF_IMG.exists():
        print(f"[error] reference image not found: {REF_IMG}")
        return

    image_b64 = encode_image(REF_IMG)
    print(f"[info] reference image: {REF_IMG} ({REF_IMG.stat().st_size} bytes)")

    # ─── (A) chart_templates (Python deterministic) ─────────────
    # Read existing LayerAgent output as the chart_templates reference
    existing = Path("results/raw/layeragent_v4/mekko_mckinsey_blue_finance_seed0.html")
    if existing.exists():
        (OUT_DIR / "A_chart_templates.html").write_bytes(existing.read_bytes())
        print(f"[A] chart_templates copy → {OUT_DIR / 'A_chart_templates.html'}")

    # ─── (B1) VLM with naive prompt ─────────────────────────────
    print("[B1] calling VLM with naive prompt...")
    out_naive = vision_call(
        image_b64,
        PROMPT_NAIVE,
        model="gpt-4o",
        max_tokens=8000,
        system_prompt="You convert design images to clean HTML+CSS. Output HTML only.",
    )
    out_naive_path = OUT_DIR / "B1_vlm_naive.html"
    out_naive_path.write_text(wrap_html(out_naive.strip(), "VLM naive"))
    print(f"[B1] → {out_naive_path} ({len(out_naive)} chars)")

    # ─── (B2) VLM with chart-aware prompt ───────────────────────
    print("[B2] calling VLM with chart-aware (mekko-specific) prompt...")
    out_aware = vision_call(
        image_b64,
        PROMPT_CHART_AWARE,
        model="gpt-4o",
        max_tokens=8000,
        system_prompt="You convert chart images to precise SVG-based HTML. Output HTML only.",
    )
    out_aware_path = OUT_DIR / "B2_vlm_chart_aware.html"
    out_aware_path.write_text(wrap_html(out_aware.strip(), "VLM chart-aware"))
    print(f"[B2] → {out_aware_path} ({len(out_aware)} chars)")

    # ─── Quick structural diff ───────────────────────────────────
    print("\n=== Structural metric ===")
    for label, p in [
        ("A. chart_templates", OUT_DIR / "A_chart_templates.html"),
        ("B1. VLM naive    ", out_naive_path),
        ("B2. VLM chart-aware", out_aware_path),
    ]:
        if not p.exists():
            continue
        txt = p.read_text()
        n_svg = txt.count("<svg")
        n_rect = txt.count("<rect")
        n_text = txt.count("<text")
        print(f"{label}: <svg>={n_svg}  <rect>={n_rect}  <text>={n_text}  size={len(txt)}b")


if __name__ == "__main__":
    run()
