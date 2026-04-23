"""Baseline B — Visual Chain-of-Thought (2-stage)."""
from __future__ import annotations

import json

from layeragent.utils.common import b64_image, extract_html, filter_content, get_design_by_id, load_meta
from layeragent.utils.llm import _openai_client


ANALYSIS_PROMPT = """이 디자인 이미지의 시각 요소를 상세히 분석해주세요.

다음을 나열해주세요:
1. 배경: 유형(단색/그라디언트/이미지/패턴), 색상, 방향
2. 카드/컨테이너: 개수, 스타일 (그림자 깊이, 모서리 반경, 테두리, 투명도, 글래스모피즘 여부)
3. 아이콘: 개수, 유형(원형 배지/인라인), 색상
4. 텍스트: 제목/본문 구분, 크기 계층, 색상
5. 장식 요소: 라인, 도형, 패턴
6. 레이어 순서
7. 시각 효과: box-shadow, glow, blur, gradient, opacity

JSON 형식으로."""

GENERATE_PROMPT = """위 분석과 아래 텍스트 콘텐츠를 바탕으로 이 디자인을 HTML+CSS로 구현하세요.

[삽입할 텍스트 콘텐츠]
{content_json}

★ 분석에서 나열된 모든 시각 요소를 반드시 코드에 포함
★ 위 텍스트 콘텐츠를 디자인 구조에 맞게 배치
★ 슬라이드 크기 1280x720px
★ <style>과 <div>로 구성된 HTML만, 설명 없이"""


def run(slide_id: str, seed: int = 0, model: str = "gpt-4o") -> str:
    client = _openai_client()
    image_b64 = b64_image(slide_id)
    meta = load_meta()
    design = get_design_by_id(meta, slide_id)
    content_json = json.dumps(filter_content(design["content"]), ensure_ascii=False, indent=2)

    # Step 1: 분석
    resp1 = client.chat.completions.create(
        model=model, max_tokens=2000,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            {"type": "text", "text": ANALYSIS_PROMPT},
        ]}],
    )
    analysis = resp1.choices[0].message.content

    # Step 2: 생성
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
                {"type": "text", "text": GENERATE_PROMPT.format(content_json=content_json)},
            ]},
        ],
    )
    return extract_html(resp2.choices[0].message.content)
