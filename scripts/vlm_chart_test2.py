"""Stronger prompt experiment: few-shot + chain-of-thought + explicit math.

If VLM still fails with this prompt, the case for chart_templates is strong.
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from layeragent.utils.llm import vision_call


REF_IMG = Path("data/eval_dataset/slides/mekko_mckinsey_blue_finance.png")
OUT_DIR = Path("results/vlm_chart_test")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────
# Strongest prompt: few-shot example + chain-of-thought + explicit math
# ─────────────────────────────────────────────────────────────────────
PROMPT_STRONG = """이 이미지는 Mekko (Marimekko) 차트입니다.
Mekko 차트를 정확한 SVG 좌표로 1280×720 단일 HTML 페이지로 재현하세요.

## Step 1 — 데이터 추출
이미지를 분석해서 다음 정보를 추출하세요:
- 슬라이드 제목 (상단 텍스트)
- 부제목 / 설명 (제목 아래 작은 텍스트)
- 4개 column 의 라벨과 비율 (예: APAC 45%, NAM 28%, EMEA 18%, LATAM 9%)
- 각 column 내 3개 segment 의 라벨과 값 (예: Apparel $35.2B, Electronics $28.8B, Home $16.0B)
- source/footer 텍스트

## Step 2 — 좌표 계산 (반드시 이 공식을 따를 것)

차트 영역 정의:
- chart_x = 80, chart_y = 200, chart_width = 1100, chart_height = 420

Column 좌표 (i = 0, 1, 2, 3):
- column_widths = [chart_width × ratio_i for i in 0..3]
  예: APAC 45% → width = 1100 × 0.45 = 495
- column_x[0] = chart_x = 80
- column_x[i] = column_x[i-1] + column_widths[i-1]
  예: NAM x = 80 + 495 = 575

Segment 좌표 (각 column 내 j = 0, 1, 2):
- column 내 segment 비율 = segment 값 / column 총합
  예: APAC 의 Apparel = 35.2 / (35.2+28.8+16.0) = 0.44
- segment_heights = [chart_height × seg_ratio_j for j in 0..2]
- segment_y[0] = chart_y = 200
- segment_y[j] = segment_y[j-1] + segment_heights[j-1]

## Step 3 — SVG 출력 (예시 형식 따를 것)

```
<!DOCTYPE html><html><head><style>
body{margin:0;font-family:'Times New Roman',serif;background:#fff;}
</style></head><body>
<div style="width:1280px;height:720px;position:relative;">
  <!-- 제목 영역: y=20~120 -->
  <text style="position:absolute;left:60px;top:30px;font-size:34px;font-weight:bold;">SLIDE_TITLE</text>
  <text style="position:absolute;left:60px;top:80px;font-size:18px;color:#888;">SUBTITLE</text>

  <!-- mekko SVG: 차트 영역 -->
  <svg width="1280" height="720" style="position:absolute;left:0;top:0;">
    <!-- column i=0 (APAC), segment j=0 (Apparel) -->
    <rect x="80" y="200" width="495" height="185" fill="#001E62"/>
    <text x="180" y="290" fill="white" font-size="16">Apparel</text>
    <text x="180" y="310" fill="white" font-size="14">$35.2B</text>
    <!-- ... 나머지 11개 rect 도 동일 패턴 ... -->

    <!-- column 라벨 (chart_y + chart_height 아래) -->
    <text x="327" y="650" text-anchor="middle" font-size="16">APAC</text>
    <text x="327" y="670" text-anchor="middle" font-size="14">45%</text>
  </svg>

  <!-- source: 우측 하단 -->
  <text style="position:absolute;right:30px;bottom:20px;font-size:11px;color:#888;">SOURCE</text>
</div></body></html>
```

## Step 4 — 검증
출력 전 다음을 확인:
1. ✓ column_widths 합이 정확히 chart_width = 1100 인가
2. ✓ 각 column 의 segment_heights 합이 정확히 chart_height = 420 인가
3. ✓ 12개 rect 모두 chart 영역 (y=200~620, x=80~1180) 안에 있는가
4. ✓ column 라벨이 viewport 안 (y < 720) 에 있는가
5. ✓ 색상은 APAC navy, 나머지 gray 계열로 일관되어 있는가

## 출력 규칙
- 순수 HTML+SVG 만 출력. ```html 같은 markdown fence 절대 사용 금지.
- 설명·주석 없이 코드만.
- <!DOCTYPE html> 로 시작."""


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def clean_html(raw: str) -> str:
    """Strip ```html fences and outer wrap."""
    txt = re.sub(r"```html\s*", "", raw)
    txt = re.sub(r"```\s*$", "", txt)
    txt = re.sub(r"```\s*\n", "", txt)
    matches = list(re.finditer(r"<!DOCTYPE html>", txt, flags=re.IGNORECASE))
    if len(matches) >= 2:
        txt = txt[matches[-1].start():]
        end = txt.lower().rfind("</html>")
        if end >= 0:
            txt = txt[: end + len("</html>")]
    return txt.strip()


def render_screenshot(html_path: Path, png_path: Path) -> None:
    from playwright.sync_api import sync_playwright
    cleaned = clean_html(html_path.read_text())
    tmp = html_path.with_suffix(".clean.html")
    tmp.write_text(cleaned)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page = ctx.new_page()
        page.goto(f"file://{tmp.resolve()}", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(png_path), clip={"x": 0, "y": 0, "width": 1280, "height": 720})
        browser.close()


def run():
    image_b64 = encode_image(REF_IMG)
    print("[B3] calling VLM with strongest prompt (few-shot + CoT + explicit math)...")
    out = vision_call(
        image_b64,
        PROMPT_STRONG,
        model="gpt-4o",
        max_tokens=12000,
        system_prompt="You are an expert SVG chart renderer. Follow the step-by-step instructions exactly. Output HTML only, no markdown fences.",
    )
    html_path = OUT_DIR / "B3_vlm_strong.html"
    html_path.write_text(out.strip())
    print(f"[B3] HTML saved → {html_path} ({len(out)} chars)")

    png_path = OUT_DIR / "B3_vlm_strong.png"
    render_screenshot(html_path, png_path)
    print(f"[B3] PNG → {png_path}")

    cleaned = clean_html(out)
    n_svg = cleaned.count("<svg")
    n_rect = cleaned.count("<rect")
    n_text = cleaned.count("<text")
    print(f"\n=== B3 structure ===")
    print(f"<svg>={n_svg}  <rect>={n_rect}  <text>={n_text}  size={len(cleaned)}b")


if __name__ == "__main__":
    run()
