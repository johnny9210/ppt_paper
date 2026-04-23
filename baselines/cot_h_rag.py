"""Baseline C — Visual CoT + Hierarchical RAG (CSS pattern knowledge injection)."""
from __future__ import annotations

import json

from layeragent.utils.common import b64_image, extract_html, filter_content, get_design_by_id, load_meta
from layeragent.utils.llm import _openai_client


# CSS pattern knowledge base
CSS_PATTERNS = {
    "gradient_linear": "background: linear-gradient({direction}, {c1}, {c2});",
    "glassmorphism": "backdrop-filter: blur(12px); background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); border-radius: 16px;",
    "card_shadow": "box-shadow: 0 4px 24px rgba(0,0,0,0.12); border-radius: 16px;",
    "neon_glow": "box-shadow: 0 0 20px rgba({r},{g},{b},0.3), 0 0 60px rgba({r},{g},{b},0.1);",
    "icon_badge_circle": "width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center;",
    "ambient_glow": "background: radial-gradient(circle, rgba({r},{g},{b},0.15), transparent 70%); filter: blur(60px);",
    "dot_pattern": "background-image: radial-gradient(circle, rgba(255,255,255,0.05) 1px, transparent 1px); background-size: 20px 20px;",
    "bottom_bar": "position:absolute;bottom:0;left:0;width:100%;height:6px;background:{color};",
}

ANALYSIS_PROMPT = """이 디자인 이미지의 시각 요소를 JSON으로 분석.
요소 타입: gradient_linear, glassmorphism, card_shadow, neon_glow, icon_badge_circle, ambient_glow, dot_pattern, bottom_bar 중에서 해당하는 것 선택.
{"elements":[{"type":"...","description":"...","params":{...}}], "layer_order":["background","cards","text","icons"]}"""


GENERATE_PROMPT = """위 분석과 CSS 패턴을 참고하여 HTML+CSS 생성.

## CSS 패턴 (해당하는 것은 반드시 이 CSS 사용):
{patterns}

[삽입할 텍스트 콘텐츠]
{content_json}

★ 분석에서 나열된 모든 요소를 코드에 포함
★ 텍스트 콘텐츠를 디자인 구조에 맞게 배치
★ 1280x720, <style>과 <div>만, 설명 없이"""


def _build_patterns_context(analysis: str) -> str:
    blocks = []
    for k, css in CSS_PATTERNS.items():
        if k.lower() in analysis.lower():
            blocks.append(f"### {k}\n```css\n{css}\n```")
    # 항상 포함
    for k in ("icon_badge_circle",):
        if k not in " ".join(blocks):
            blocks.append(f"### {k}\n```css\n{CSS_PATTERNS[k]}\n```")
    return "\n\n".join(blocks)


def run(slide_id: str, seed: int = 0, model: str = "gpt-4o") -> str:
    client = _openai_client()
    image_b64 = b64_image(slide_id)
    meta = load_meta()
    design = get_design_by_id(meta, slide_id)
    content_json = json.dumps(filter_content(design["content"]), ensure_ascii=False, indent=2)

    resp1 = client.chat.completions.create(
        model=model, max_tokens=2000,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            {"type": "text", "text": ANALYSIS_PROMPT},
        ]}],
    )
    analysis = resp1.choices[0].message.content
    patterns = _build_patterns_context(analysis)

    resp2 = client.chat.completions.create(
        model=model, max_tokens=8000,
        messages=[
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": ANALYSIS_PROMPT},
            ]},
            {"role": "assistant", "content": analysis},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": GENERATE_PROMPT.format(patterns=patterns, content_json=content_json)},
            ]},
        ],
    )
    return extract_html(resp2.choices[0].message.content)
