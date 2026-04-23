"""
Method C: Visual CoT + H-RAG — 분석 후 CSS 패턴을 검색하여 코드 생성.
VLM의 인식 + 검증된 CSS 패턴으로 시각 정보 손실을 최소화.
"""

from openai import OpenAI

# ── CSS Pattern Knowledge Base ──

CSS_PATTERNS = {
    "gradient_linear": {
        "description": "선형 그라디언트 배경",
        "css": "background: linear-gradient({direction}, {color1}, {color2});",
        "example": "background: linear-gradient(135deg, #0F172A, #1E293B);",
    },
    "gradient_radial": {
        "description": "방사형 그라디언트",
        "css": "background: radial-gradient(circle at {position}, {color1}, {color2});",
        "example": "background: radial-gradient(circle at 30% 70%, rgba(59,130,246,0.15), transparent 50%);",
    },
    "glassmorphism": {
        "description": "글래스모피즘 카드 (반투명 블러 효과)",
        "css": "backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); border-radius: 16px;",
    },
    "card_shadow": {
        "description": "카드 그림자",
        "css": "box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12); border-radius: 16px;",
    },
    "neon_glow": {
        "description": "네온 글로우 효과",
        "css": "box-shadow: 0 0 20px rgba({r},{g},{b}, 0.3), 0 0 60px rgba({r},{g},{b}, 0.1);",
    },
    "icon_badge_circle": {
        "description": "원형 아이콘 배지",
        "css": "width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: {color};",
        "content": '<i class="fas fa-{icon}" style="color: #fff; font-size: 20px;"></i>',
    },
    "icon_badge_rounded": {
        "description": "둥근 사각형 아이콘 배지",
        "css": "width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; background: {color};",
        "content": '<i class="fas fa-{icon}" style="color: #fff; font-size: 20px;"></i>',
    },
    "layer_stack": {
        "description": "요소 겹침 (레이어 순서)",
        "css": "position: relative; /* 부모 컨테이너 */\n/* 자식 요소들: */ position: absolute; z-index: {order};",
        "note": "z-index 값: 0=배경, 1=장식, 2=카드, 3=텍스트, 4=아이콘",
    },
    "ambient_glow": {
        "description": "분위기 광원 효과",
        "css": "position: absolute; width: 300px; height: 300px; border-radius: 50%; background: radial-gradient(circle, rgba({r},{g},{b},0.15), transparent 70%); filter: blur(60px);",
    },
    "dot_pattern": {
        "description": "도트 패턴 배경",
        "css": "background-image: radial-gradient(circle, rgba(255,255,255,0.05) 1px, transparent 1px); background-size: 20px 20px;",
    },
    "accent_line": {
        "description": "액센트 구분선",
        "css": "width: 48px; height: 4px; border-radius: 2px; background: {color};",
    },
    "bottom_bar": {
        "description": "하단 컬러 바",
        "css": "position: absolute; bottom: 0; left: 0; width: 100%; height: 6px; background: {color};",
    },
}

ANALYSIS_PROMPT = """이 디자인 이미지의 시각 요소를 분석해주세요.

각 요소를 다음 유형 중에서 분류해주세요:
- gradient_linear, gradient_radial (배경)
- glassmorphism, card_shadow, neon_glow (카드 효과)
- icon_badge_circle, icon_badge_rounded (아이콘)
- layer_stack (겹치는 요소)
- ambient_glow (분위기 광원)
- dot_pattern (배경 패턴)
- accent_line, bottom_bar (장식)

JSON 형식으로 출력:
{
  "elements": [
    {"type": "gradient_linear", "description": "어두운 남색 그라디언트 배경", "params": {"direction": "135deg", "color1": "#0F172A", "color2": "#1E293B"}},
    {"type": "glassmorphism", "description": "반투명 카드 3개", "count": 3},
    ...
  ],
  "layer_order": ["background", "decoration", "cards", "text", "icons"]
}"""


def _build_pattern_context(analysis: str) -> str:
    """분석 결과에서 언급된 유형의 CSS 패턴을 검색."""
    context_parts = []
    for key, pattern in CSS_PATTERNS.items():
        if key in analysis.lower() or key.replace("_", " ") in analysis.lower():
            css = pattern["css"]
            example = pattern.get("example", "")
            content = pattern.get("content", "")
            note = pattern.get("note", "")
            entry = f"### {key}: {pattern['description']}\n```css\n{css}\n```"
            if example:
                entry += f"\nExample: `{example}`"
            if content:
                entry += f"\nHTML: `{content}`"
            if note:
                entry += f"\nNote: {note}"
            context_parts.append(entry)

    # 항상 포함하는 기본 패턴
    for must_include in ["layer_stack", "icon_badge_circle"]:
        if must_include not in " ".join(context_parts):
            p = CSS_PATTERNS[must_include]
            context_parts.append(f"### {must_include}: {p['description']}\n```css\n{p['css']}\n```")

    return "\n\n".join(context_parts)


GENERATE_PROMPT = """위 분석과 아래 CSS 패턴을 참고하여 HTML+CSS를 생성하세요.

## 검증된 CSS 패턴 (반드시 해당하는 패턴을 사용하세요)

{patterns}

★ 중요 규칙:
1. 위 패턴에 해당하는 시각 요소는 반드시 해당 CSS를 사용하세요
2. 분석에서 나열된 모든 요소를 코드에 포함하세요
3. layer_order에 따라 z-index를 명시하세요
4. 아이콘은 반드시 FontAwesome 또는 이모지로 (<img> 금지)
5. 슬라이드 크기: 1280x720px
6. <style>과 <div>로 구성된 HTML 코드만 출력
7. JavaScript 금지
8. 코드만 출력 (설명 없이)"""


def generate(client: OpenAI, image_b64: str, model: str = "gpt-4o") -> tuple[str, str, str]:
    """Returns (analysis, patterns_used, html_code)."""
    # Step 1: 시각 요소 분석 + 유형 분류
    resp1 = client.chat.completions.create(
        model=model,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": ANALYSIS_PROMPT},
            ],
        }],
    )
    analysis = resp1.choices[0].message.content

    # Step 2: H-RAG — 분류된 유형에 맞는 CSS 패턴 검색
    patterns = _build_pattern_context(analysis)

    # Step 3: 패턴 보강 코드 생성
    resp2 = client.chat.completions.create(
        model=model,
        max_tokens=8000,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    {"type": "text", "text": ANALYSIS_PROMPT},
                ],
            },
            {"role": "assistant", "content": analysis},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    {"type": "text", "text": GENERATE_PROMPT.format(patterns=patterns)},
                ],
            },
        ],
    )
    html_code = resp2.choices[0].message.content

    return analysis, patterns, html_code


GENERATE_PROMPT_WITH_CONTENT = """위 분석과 아래 CSS 패턴을 참고하여 HTML+CSS를 생성하세요.

## 검증된 CSS 패턴
{patterns}

[삽입할 텍스트 콘텐츠]
{content_json}

★ 중요 규칙:
1. 위 패턴에 해당하는 시각 요소는 반드시 해당 CSS를 사용
2. 위 텍스트 콘텐츠를 디자인 구조에 맞게 배치
3. layer_order에 따라 z-index를 명시
4. 아이콘은 반드시 FontAwesome 또는 이모지 (<img> 금지)
5. 슬라이드 크기: 1280x720px
6. <style>과 <div>로 구성된 HTML 코드만 출력
7. JavaScript 금지
8. 코드만 출력 (설명 없이)"""


def generate_with_content(client: OpenAI, image_b64: str, content: dict, model: str = "gpt-4o") -> tuple[str, str, str]:
    """Fair comparison: content 데이터도 함께 제공."""
    import json
    skip = {"speaker_script", "infographic_script"}
    filtered = {k: v for k, v in content.items() if k not in skip}
    content_json = json.dumps(filtered, ensure_ascii=False, indent=2)

    resp1 = client.chat.completions.create(
        model=model, max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": ANALYSIS_PROMPT},
            ],
        }],
    )
    analysis = resp1.choices[0].message.content
    patterns = _build_pattern_context(analysis)

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
                {"type": "text", "text": GENERATE_PROMPT_WITH_CONTENT.format(patterns=patterns, content_json=content_json)},
            ]},
        ],
    )
    return analysis, patterns, resp2.choices[0].message.content
