"""Unified LLM call helpers (OpenAI direct). Also supports Azure / Bedrock via explicit wrappers."""
from __future__ import annotations

import base64
import os

from openai import OpenAI


SYSTEM_PROMPT_DEFAULT = """당신은 디자인 이미지를 HTML+CSS로 변환하는 전문가입니다.
★ <style>과 <div>로 구성된 순수 HTML 코드만 출력하세요. 설명 없이.
★ CSS 효과를 최대한 풍부하게 사용: gradient, box-shadow, backdrop-filter, opacity, border-radius.
★ JavaScript 금지, <img> 금지."""


_CLIENT = None


def _openai_client() -> OpenAI:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = OpenAI()
    return _CLIENT


def vision_call(
    image_b64: str,
    prompt: str,
    model: str = "gpt-4o",
    max_tokens: int = 10000,
    system_prompt: str = SYSTEM_PROMPT_DEFAULT,
) -> str:
    client = _openai_client()
    header = base64.b64decode(image_b64[:16])
    mime = "image/png" if header[:4] == b"\x89PNG" else "image/jpeg"
    resp = client.chat.completions.create(
        model=model, max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ]},
        ],
    )
    return resp.choices[0].message.content


def text_call(prompt: str, model: str = "gpt-4o", max_tokens: int = 8000) -> str:
    client = _openai_client()
    resp = client.chat.completions.create(
        model=model, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content
