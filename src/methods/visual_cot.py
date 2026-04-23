"""
Method B: Visual Chain-of-Thought — 먼저 시각 요소를 분석한 후 코드 생성.
VLM의 인식 능력을 명시적으로 활용하여 generation gap을 줄임.
"""

from openai import OpenAI

ANALYSIS_PROMPT = """이 디자인 이미지의 시각 요소를 상세히 분석해주세요.

다음을 나열해주세요:
1. 배경: 유형(단색/그라디언트/이미지/패턴), 색상, 방향
2. 카드/컨테이너: 개수, 스타일(그림자 깊이, 모서리 반경, 테두리, 투명도, 글래스모피즘 여부)
3. 아이콘: 개수, 유형(원형 배지/인라인), 색상
4. 텍스트: 제목/본문 구분, 크기 계층, 색상
5. 장식 요소: 라인, 도형, 패턴
6. 레이어 순서: 가장 뒤(z=0)부터 가장 앞까지 순서대로
7. 시각 효과: box-shadow, glow, blur, gradient, opacity 등

JSON 형식으로 출력해주세요."""

GENERATE_PROMPT = """위 분석을 바탕으로 이 디자인을 HTML+CSS로 구현하세요.

★ 중요: 분석에서 나열된 모든 시각 요소를 반드시 코드에 포함하세요.
- 배경 유형과 색상을 정확히 구현
- 카드의 그림자, 모서리, 투명도를 모두 CSS로 구현
- 아이콘은 FontAwesome(<i class="fas fa-...">)이나 이모지로 구현
- 레이어 순서대로 z-index를 명시
- 나열된 모든 시각 효과(shadow, glow, blur 등)를 CSS로 구현

규칙:
- 슬라이드 크기: 1280x720px
- <style>과 <div>로 구성된 HTML 코드만 출력
- JavaScript 금지, <img> 태그 금지
- 코드만 출력 (설명 없이)"""


def generate(client: OpenAI, image_b64: str, model: str = "gpt-4o") -> tuple[str, str]:
    """Returns (analysis, html_code)."""
    # Step 1: 시각 요소 분석
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

    # Step 2: 분석 기반 코드 생성
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
                    {"type": "text", "text": GENERATE_PROMPT},
                ],
            },
        ],
    )
    html_code = resp2.choices[0].message.content

    return analysis, html_code


GENERATE_PROMPT_WITH_CONTENT = """위 분석을 바탕으로 이 디자인을 HTML+CSS로 구현하세요.

[삽입할 텍스트 콘텐츠]
{content_json}

★ 중요: 분석에서 나열된 모든 시각 요소를 반드시 코드에 포함하세요.
★ 위 텍스트 콘텐츠를 디자인 구조에 맞게 배치하세요.
- 배경 유형과 색상을 정확히 구현
- 카드의 그림자, 모서리, 투명도를 모두 CSS로 구현
- 아이콘은 FontAwesome(<i class="fas fa-...">)이나 이모지로 구현
- 레이어 순서대로 z-index를 명시

규칙:
- 슬라이드 크기: 1280x720px
- <style>과 <div>로 구성된 HTML 코드만 출력
- JavaScript 금지, <img> 태그 금지
- 코드만 출력 (설명 없이)"""


def generate_with_content(client: OpenAI, image_b64: str, content: dict, model: str = "gpt-4o") -> tuple[str, str]:
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
                {"type": "text", "text": GENERATE_PROMPT_WITH_CONTENT.format(content_json=content_json)},
            ]},
        ],
    )
    return analysis, resp2.choices[0].message.content
