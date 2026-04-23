"""Visual Critic Agent — 렌더된 결과를 원본과 비교해 구체적 diff 출력 후 change-only 수정.

Vision-Guided Iterative Refinement (arxiv:2604.05839) 방식.
1 iteration only — cascade 위험 방지.

Flow:
1. assembled HTML → Playwright 렌더 → PNG
2. Critic VLM (Claude): [reference image, rendered PNG] → 구조화된 diff JSON
3. Fixer (text LLM): [HTML, diff JSON] → 수정된 HTML
"""
from __future__ import annotations

import base64
import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from . import _common
from src.methods import crop_layer_agent as _la


# ════════════════════════════════════════════════════════════
# Rendering via Playwright
# ════════════════════════════════════════════════════════════

def render_html_to_b64(html_content: str, width: int = 1280, height: int = 720) -> str:
    """HTML 문자열을 Playwright로 렌더 후 PNG base64 반환."""
    from playwright.sync_api import sync_playwright

    wrapped = _common.wrap_slide(html_content)
    tmp = Path("/tmp/visual_critic_render.html")
    tmp.write_text(wrapped)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=2)
        page = ctx.new_page()
        try:
            page.goto(f"file://{tmp.resolve()}", wait_until="networkidle", timeout=15000)
        except Exception:
            page.goto(f"file://{tmp.resolve()}", wait_until="load", timeout=15000)
        page.wait_for_timeout(400)
        png_bytes = page.screenshot(clip={"x": 0, "y": 0, "width": width, "height": height})
        browser.close()

    return base64.b64encode(png_bytes).decode()


# ════════════════════════════════════════════════════════════
# Critic — Reference vs Rendered 비교
# ════════════════════════════════════════════════════════════

CRITIC_PROMPT = """당신은 시각 충실도 감사관이다. 두 이미지를 비교한다:
- **REFERENCE** — 재현해야 할 원본 디자인
- **RENDERED** — 현재 HTML/CSS 출력

두 이미지의 **구체적이고 수정 가능한** 차이를 찾아내라.

집중해야 할 diff 카테고리:
1. **background_color**: 배경 색이 hex 수준에서 다름 (예: reference는 #0E1931 네이비, rendered는 갈색)
2. **missing_element**: reference에 있는데 rendered에 없는 요소 (예: hero frame, 기하 도형, bottom accent bar)
3. **extra_element**: rendered에 있는데 reference에 없는 orphan 장식
4. **typography**: 폰트 family/weight/size/color 미스매치 (특히 hero value)
5. **layout_overflow**: 텍스트가 컨테이너를 넘침, 위치가 박스 밖
6. **color_drift**: 같은 요소의 색이 reference와 다름
7. **size_proportion**: 요소 크기 비율이 reference와 다름

**중요**:
- 사소한 미세 차이(1~2px)는 무시
- 내용 텍스트(예: "XXXX" vs "300%")는 OK — 플레이스홀더 → 실제 값 대체는 의도된 것
- 스타일·컬러·레이아웃의 *시각적* 차이에만 집중

다음 JSON만 출력 (설명 없이):
```json
{
  "diffs": [
    {
      "category": "background_color",
      "severity": "high",
      "observed": "rendered has brown-gray background",
      "expected": "reference has deep navy #0E1931",
      "fix_hint": "Change body/container background to linear-gradient(135deg, #0E1931, #1C2D49)"
    },
    {
      "category": "layout_overflow",
      "severity": "high",
      "observed": "hero value text overflows left edge of hero container",
      "expected": "text should fit inside hero box",
      "fix_hint": "Reduce .hero-value font-size to clamp(2rem, 15%, 5rem) or add overflow:hidden + text scaling"
    }
  ],
  "overall_fidelity": 0.xx
}
```

severity: high | medium | low — 시각 임팩트 기준
최대 8개 diff만. 가장 중요한 것부터."""


def run_critic(reference_b64: str, rendered_b64: str, model: str = "gpt-4o") -> dict:
    """두 이미지 비교하여 diff JSON 반환."""
    from openai import OpenAI
    client = OpenAI()

    resp = client.chat.completions.create(
        model=model, max_tokens=3000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": CRITIC_PROMPT},
                {"type": "text", "text": "REFERENCE 이미지:"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{reference_b64}"}},
                {"type": "text", "text": "RENDERED 이미지 (현재 HTML 출력):"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{rendered_b64}"}},
            ],
        }],
    )
    raw = resp.choices[0].message.content
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {"diffs": [], "overall_fidelity": 0.0, "raw": raw[:500]}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"diffs": [], "overall_fidelity": 0.0, "raw": raw[:500]}


# ════════════════════════════════════════════════════════════
# Fixer — HTML에 diff 반영
# ════════════════════════════════════════════════════════════

FIXER_PROMPT = """아래 HTML을 **구체적 diff 목록**에 따라 수정하라.

**현재 HTML**:
```html
{html}
```

**수정해야 할 diff 목록**:
```json
{diffs}
```

★★★ 수정 원칙 (change-only):
1. diff 목록에 있는 항목만 수정 — 다른 부분 변경 금지
2. HTML 구조(div 계층, class 이름, 순서) 절대 변경 금지
3. CSS 속성값만 변경 — 새 요소 추가 / 삭제 금지 (단, diff.category == "extra_element" 에서 제거 요청은 예외)
4. 각 diff의 fix_hint를 따르되, 기존 HTML 스타일 일관성 유지

★ 전체 수정된 HTML 출력 (`<style>`과 `<div>` 만)
★ 설명·주석 없이 코드만"""


def run_fixer(html: str, diffs: dict, model: str = "gpt-4o") -> str:
    """diff 적용한 HTML 반환."""
    from openai import OpenAI
    client = OpenAI()

    diff_summary = json.dumps(diffs.get("diffs", [])[:8], ensure_ascii=False, indent=2)
    prompt = FIXER_PROMPT.format(html=html[:30000], diffs=diff_summary)

    resp = client.chat.completions.create(
        model=model, max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.choices[0].message.content
    result = _la._extract_html(raw)
    if not result or len(result) < 500:
        return html  # fallback to original
    return result


# ════════════════════════════════════════════════════════════
# Visual Critic node — pipeline integration
# ════════════════════════════════════════════════════════════

def visual_critic_node(state) -> dict:
    """렌더 → critic → fix. 1 iteration only."""
    html = state.get("assembled", "")
    if not html or len(html) < 200:
        return {"assembled": html, "critic_diffs": None}

    # 1. Render
    try:
        rendered_b64 = render_html_to_b64(html)
    except Exception as e:
        print(f"[critic] render failed: {e}")
        return {"assembled": html, "critic_diffs": None}

    # 2. Critic: reference vs rendered → diffs
    reference_b64 = state["image_b64"]
    try:
        diffs = run_critic(reference_b64, rendered_b64, model=state.get("model", "gpt-4o"))
    except Exception as e:
        print(f"[critic] critic failed: {e}")
        return {"assembled": html, "critic_diffs": None}

    n_diffs = len(diffs.get("diffs", []))
    fidelity = diffs.get("overall_fidelity", 0)
    print(f"[critic] {n_diffs} diffs identified, fidelity≈{fidelity:.2f}")

    if n_diffs == 0:
        return {"assembled": html, "critic_diffs": diffs}

    # 3. Fixer: HTML에 diff 반영
    try:
        fixed_html = run_fixer(html, diffs, model=state.get("model", "gpt-4o"))
    except Exception as e:
        print(f"[critic] fixer failed: {e}")
        return {"assembled": html, "critic_diffs": diffs}

    return {"assembled": fixed_html, "critic_diffs": diffs}
