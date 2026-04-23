"""
Method D: Visual CoT + H-RAG + Verification Loop (Full Pipeline)

Step 1: Visual CoT — 이미지 분석 + CSS 계획
Step 2: H-RAG — 식별된 요소 유형에 맞는 CSS 패턴 + 금지 규칙 검색
Step 3: 2-Pass 생성 — 분석 + 패턴으로 레이아웃(Pass1) → 텍스트 삽입(Pass2)
Step 4: 메트릭 검증 — 실패 시 구체적 피드백 후 재생성
"""

import json
import re
from openai import OpenAI


# ══════════════════════════════════════
# H-RAG Knowledge Base
# ══════════════════════════════════════

CSS_KNOWLEDGE_BASE = {
    # ── 배경 패턴 ──
    "gradient_linear": {
        "pattern": "background: linear-gradient({direction}, {color1}, {color2});",
        "example": "background: linear-gradient(135deg, #0F172A, #1E293B);",
    },
    "gradient_radial": {
        "pattern": "background: radial-gradient(circle at {pos}, {color1}, transparent {radius});",
        "example": "background: radial-gradient(circle at 30% 70%, rgba(59,130,246,0.15), transparent 50%);",
    },
    # ── 카드 효과 ──
    "glassmorphism": {
        "pattern": "backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); border-radius: 16px;",
    },
    "card_basic": {
        "pattern": "background: #fff; border-radius: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border: 1px solid #E2E8F0;",
    },
    "neon_glow": {
        "pattern": "box-shadow: 0 0 20px rgba({r},{g},{b}, 0.3), 0 0 60px rgba({r},{g},{b}, 0.1);",
    },
    # ── 아이콘 ──
    "icon_circle": {
        "pattern": "width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: {color};",
        "content": '<i class="fas fa-{icon}" style="color:#fff;font-size:20px;"></i>',
    },
    # ── 레이어링 ──
    "layer_stack": {
        "pattern": "position: relative; /* parent */ position: absolute; z-index: {n}; /* children */",
        "note": "z-index: 0=bg, 1=decoration, 2=card, 3=text, 4=icon",
    },
    # ── 장식 ──
    "accent_line": {
        "pattern": "width: 48px; height: 4px; border-radius: 2px; background: {color};",
    },
    "bottom_bar": {
        "pattern": "position: absolute; bottom: 0; left: 0; width: 100%; height: 6px; background: {color};",
    },
}

# ── 금지 규칙 (프로덕션에서 발견된 실패 패턴) ──
PROHIBITION_RULES = """
## 금지 규칙 (이것을 사용하면 렌더링이 깨집니다)
- ❌ clip-path 사용 금지
- ❌ filter: blur() 사용 금지 (backdrop-filter는 허용)
- ❌ box-shadow 3개 이상 중첩 금지
- ❌ transparent 키워드를 gradient stop에 사용 금지 → rgba(배경색,0) 대신 사용
- ❌ 글래스모피즘 오버레이 (rgba alpha 0.05~0.1 반투명 레이어) 금지 → 불투명하게 변환됨
- ❌ 풀사이즈 장식 div (width:100%, height:100%, position:absolute) 위에 그라디언트 금지
- ❌ ::before/::after + border/box-shadow로 아이콘 그리기 금지 → FontAwesome 또는 이모지 사용
- ❌ content: "" + CSS로 도형 만들기 금지
- ❌ 텍스트 요소 간 position:absolute로 겹치게 배치 금지 → 최소 font-size * 1.5 간격
- ❌ 반투명 배경 div (rgba alpha < 0.4)를 텍스트 뒤에 깔기 금지
- ✅ 텍스트가 있는 컨테이너는 불투명 배경 (alpha >= 0.8) 사용
- ✅ 제목과 부제목 사이 최소 10px 간격
- ❌ 다중 radial-gradient 배경 레이어 금지 → 단일 gradient만
"""

# ══════════════════════════════════════
# Prompts
# ══════════════════════════════════════

STEP1_ANALYSIS = """이 디자인 이미지의 시각 요소를 상세히 분석해주세요.

각 요소를 다음 유형으로 분류하고, 필요한 CSS 속성을 구체적으로 명시해주세요:

1. **배경**: gradient_linear / gradient_radial / solid → 색상, 방향
2. **카드**: glassmorphism / card_basic / neon_glow → 투명도, 모서리, 그림자
3. **아이콘**: icon_circle → 색상, FontAwesome 아이콘명
4. **텍스트 영역**: 위치, 크기 (내용은 분석하지 마세요)
5. **장식**: accent_line / bottom_bar / 기타
6. **레이어 순서**: z-index 0(배경)부터 순서대로 나열

JSON 형식으로 출력:
{
  "background": {"type": "gradient_linear", "direction": "135deg", "colors": ["#0F172A", "#1E293B"]},
  "elements": [
    {"type": "glassmorphism", "id": "main_card", "position": "left 5%, top 10%", "size": "50% x 80%", "z_order": 2},
    {"type": "icon_circle", "id": "icon1", "color": "#3B82F6", "icon": "fa-shield-halved", "z_order": 4}
  ],
  "layer_order": ["background(0)", "decorations(1)", "cards(2)", "text(3)", "icons(4)"]
}"""

STEP3_PASS1 = """위 분석과 아래 CSS 패턴/금지 규칙을 참고하여 레이아웃 HTML을 생성하세요.

## 검증된 CSS 패턴
{patterns}

{prohibitions}

★ 핵심 규칙:
1. 분석에서 나열된 모든 시각 요소를 반드시 구현
2. layer_order대로 z-index를 명시적으로 설정
3. 아이콘은 FontAwesome <i class="fas fa-..."> 또는 이모지만 사용
4. 텍스트는 넣지 마세요 — 텍스트 들어갈 빈 영역만
5. 슬라이드: 1280x720px
6. CSS 선택자는 .{slide_id}로 스코핑
7. 컨테이너: <div class="slide-container {slide_id}">
8. <style>과 <div>로 구성된 HTML만 출력
9. JavaScript 금지, <img> 태그 금지"""

STEP3_PASS2 = """위 HTML 레이아웃의 빈 영역에 텍스트를 삽입하세요.

[삽입할 콘텐츠]
{content_json}

★ 삽입 후 반드시 자체 검수:
[체크 1] 텍스트 오버플로우 — 각 텍스트 영역의 글자 수와 컨테이너 크기 비교
  넘칠 경우: font-size 축소 → line-height 축소 → padding 축소 → 텍스트 축약
[체크 2] absolute 자식이 부모 밖으로 나가는지 — top+height, left+width 확인
[체크 3] 1280×720 범위 초과 — 모든 콘텐츠가 슬라이드 안에 있는지

문제 발견 시 수정 후 최종본만 출력하세요.
레이아웃 구조를 변경하지 마세요. <style>과 <div> HTML만 출력."""


def _build_patterns_for_analysis(analysis: str) -> str:
    """분석 결과에서 언급된 유형의 CSS 패턴을 검색."""
    parts = []
    for key, info in CSS_KNOWLEDGE_BASE.items():
        if key.replace("_", " ") in analysis.lower() or key in analysis.lower() or key.split("_")[0] in analysis.lower():
            entry = f"**{key}**: `{info['pattern']}`"
            if "example" in info:
                entry += f"\n  Example: `{info['example']}`"
            if "content" in info:
                entry += f"\n  HTML: `{info['content']}`"
            if "note" in info:
                entry += f"\n  Note: {info['note']}"
            parts.append(entry)

    # 항상 포함
    for must in ["layer_stack", "icon_circle"]:
        if must not in " ".join(parts):
            info = CSS_KNOWLEDGE_BASE[must]
            parts.append(f"**{must}**: `{info['pattern']}`")

    return "\n".join(parts) if parts else "일반적인 CSS 패턴을 사용하세요."


def _extract_html(text: str) -> str:
    text = text.strip()
    if "```html" in text:
        text = text.split("```html", 1)[1].split("```")[0]
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
    start = re.search(r"<(?:style|div|!DOCTYPE)", text, re.IGNORECASE)
    if start and start.start() > 0:
        text = text[start.start():]
    return text.strip()


def generate(
    client: OpenAI,
    image_b64: str,
    slide_id: str,
    slide_type: str,
    content: dict,
    style: dict,
    model: str = "gpt-4o",
) -> dict:
    """Full pipeline: Visual CoT + H-RAG + 2-Pass + Verification."""

    # ── Step 1: Visual CoT 분석 ──
    resp1 = client.chat.completions.create(
        model=model, max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": STEP1_ANALYSIS},
            ],
        }],
    )
    analysis = resp1.choices[0].message.content

    # ── Step 2: H-RAG 패턴 검색 ──
    patterns = _build_patterns_for_analysis(analysis)

    # ── Step 3: 2-Pass 생성 ──
    # Pass 1: 레이아웃 (텍스트 없이)
    pass1_prompt = STEP3_PASS1.format(
        patterns=patterns,
        prohibitions=PROHIBITION_RULES,
        slide_id=slide_id,
    )

    resp2 = client.chat.completions.create(
        model=model, max_tokens=8000,
        messages=[
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": STEP1_ANALYSIS},
            ]},
            {"role": "assistant", "content": analysis},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": pass1_prompt},
            ]},
        ],
    )
    layout_html = _extract_html(resp2.choices[0].message.content)

    # Pass 2: 텍스트 삽입 + 자체 검수
    content_json = json.dumps(content, ensure_ascii=False, indent=2)
    pass2_prompt = STEP3_PASS2.format(content_json=content_json)

    resp3 = client.chat.completions.create(
        model=model, max_tokens=8000,
        messages=[
            {"role": "user", "content": f"[레이아웃 HTML]\n```html\n{layout_html}\n```"},
            {"role": "user", "content": pass2_prompt},
        ],
    )
    final_html = _extract_html(resp3.choices[0].message.content)

    return {
        "analysis": analysis,
        "patterns_used": patterns,
        "layout_html": layout_html,
        "final_html": final_html,
    }
