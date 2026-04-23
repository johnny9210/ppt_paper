"""
Method B+: Visual CoT + 2-Pass — 같은 Gemini 디자인 이미지를 받고,
먼저 시각 요소를 분석한 후 2-pass로 HTML 생성 (규칙 없이).

원본 AIDX PPT와 같은 조건(같은 Gemini 이미지)에서 비교하기 위한 방법.
"""

from openai import OpenAI

ANALYSIS_PROMPT = """이 디자인 이미지의 시각 요소를 상세히 분석해주세요.

다음을 나열해주세요:
1. 배경: 유형(단색/그라디언트/이미지/패턴), 색상, 방향
2. 카드/컨테이너: 개수, 스타일(그림자 깊이, 모서리 반경, 테두리, 투명도, 글래스모피즘 여부)
3. 아이콘: 개수, 유형(원형 배지/인라인), 색상
4. 텍스트 영역: 위치, 크기 (텍스트 내용은 분석하지 마세요)
5. 장식 요소: 라인, 도형, 패턴, 광원 효과
6. 레이어 순서: 가장 뒤(z=0)부터 가장 앞까지 순서대로
7. 시각 효과: box-shadow, glow, blur, gradient, opacity 등

각 요소의 대략적인 위치(좌상단 기준 %)와 크기도 포함해주세요."""

PASS1_PROMPT = """위 분석을 바탕으로 이 디자인 이미지의 시각적 구조를 HTML + CSS로 정확히 재현하세요.

★ 핵심: 텍스트 콘텐츠는 렌더링하지 않습니다 — 텍스트가 들어갈 구조만 잡아둡니다.

규칙:
- 분석에서 나열된 모든 시각 요소(배경, 카드, 아이콘, 장식, 효과)를 반드시 CSS로 구현
- 레이어 순서대로 z-index를 명시
- 아이콘은 FontAwesome(<i class="fas fa-...">)이나 이모지로 구현
- 텍스트가 들어갈 자리에 적절한 높이/여백의 빈 영역만 만드세요
- 슬라이드 크기: 1280x720px
- 모든 CSS 선택자는 .{slide_id}로 스코핑
- 컨테이너: <div class="slide-container {slide_id}">
- <style>과 <div>로 구성된 HTML 코드만 출력
- JavaScript 금지, <img> 태그 금지
- 코드만 출력 (설명 없이)"""

PASS2_PROMPT = """위 HTML 레이아웃의 빈 영역에 아래 텍스트 콘텐츠를 삽입하세요.

[삽입할 콘텐츠]
{content_json}

규칙:
- 레이아웃 구조(CSS, 카드 배치, 색상)는 그대로 유지
- 텍스트와 아이콘만 추가
- 배경 대비 텍스트 가독성 보장
- 텍스트가 넘치면: font-size 축소 → padding 축소 → 텍스트 축약 순서로 조정
- <style>과 <div>로 구성된 HTML 코드만 출력
- 코드만 출력 (설명 없이)"""


def generate(
    client: OpenAI,
    image_b64: str,
    slide_id: str,
    slide_type: str,
    content: dict,
    style: dict,
    model: str = "gpt-4o",
) -> tuple[str, str, str]:
    """Returns (analysis, layout_html, final_html)."""
    import json

    # Step 1: 시각 요소 분석 (Visual CoT)
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

    # Step 2: Pass 1 — 분석 기반 레이아웃 생성 (텍스트 없이)
    pass1_prompt = PASS1_PROMPT.replace("{slide_id}", slide_id)
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
                    {"type": "text", "text": pass1_prompt},
                ],
            },
        ],
    )
    layout_html = resp2.choices[0].message.content

    # Step 3: Pass 2 — 텍스트 삽입
    content_json = json.dumps(content, ensure_ascii=False, indent=2)
    resp3 = client.chat.completions.create(
        model=model,
        max_tokens=8000,
        messages=[
            {"role": "user", "content": f"[레이아웃 HTML]\n```html\n{layout_html}\n```"},
            {
                "role": "user",
                "content": PASS2_PROMPT.format(content_json=content_json),
            },
        ],
    )
    final_html = resp3.choices[0].message.content

    return analysis, layout_html, final_html
