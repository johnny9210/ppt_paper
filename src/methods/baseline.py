"""
Method A: Baseline — 이미지를 보고 바로 HTML 생성.
현재 대부분의 design-to-code 시스템이 하는 방식.
"""

from openai import OpenAI

PROMPT = """이 디자인 이미지를 HTML+CSS로 변환하세요.

규칙:
- 슬라이드 크기: 1280x720px
- 이미지의 시각적 구조를 최대한 정확히 재현
- <style>과 <div>로 구성된 HTML 코드만 출력
- JavaScript 금지, <img> 태그 금지
- 코드만 출력 (설명 없이)"""


def generate(client: OpenAI, image_b64: str, model: str = "gpt-4o") -> str:
    resp = client.chat.completions.create(
        model=model,
        max_tokens=8000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )
    return resp.choices[0].message.content


PROMPT_WITH_CONTENT = """이 디자인 이미지를 HTML+CSS로 변환하세요.

[삽입할 텍스트 콘텐츠]
{content_json}

규칙:
- 슬라이드 크기: 1280x720px
- 이미지의 시각적 구조를 최대한 정확히 재현
- 위 텍스트 콘텐츠를 디자인에 맞게 배치
- <style>과 <div>로 구성된 HTML 코드만 출력
- JavaScript 금지, <img> 태그 금지
- 코드만 출력 (설명 없이)"""


def generate_with_content(client: OpenAI, image_b64: str, content: dict, model: str = "gpt-4o") -> str:
    """Fair comparison: content 데이터도 함께 제공."""
    import json
    skip = {"speaker_script", "infographic_script"}
    filtered = {k: v for k, v in content.items() if k not in skip}
    content_json = json.dumps(filtered, ensure_ascii=False, indent=2)

    resp = client.chat.completions.create(
        model=model,
        max_tokens=8000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": PROMPT_WITH_CONTENT.format(content_json=content_json)},
            ],
        }],
    )
    return resp.choices[0].message.content
