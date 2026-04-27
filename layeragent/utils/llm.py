"""Unified LLM call helpers (OpenAI direct). Also supports Azure / Bedrock via explicit wrappers.

Token usage tracking — when TRACK_TOKENS env var is set, every vision_call /
text_call appends to TOKEN_LOG (a list of {model, prompt_tokens, completion_tokens}).
Used by experiments to measure LayerAgent's cumulative token cost.
"""
from __future__ import annotations

import base64
import os

from openai import OpenAI


SYSTEM_PROMPT_DEFAULT = """당신은 디자인 이미지를 HTML+CSS로 변환하는 전문가입니다.
★ <style>과 <div>로 구성된 순수 HTML 코드만 출력하세요. 설명 없이.
★ CSS 효과를 최대한 풍부하게 사용: gradient, box-shadow, backdrop-filter, opacity, border-radius.
★ JavaScript 금지, <img> 금지."""


_CLIENT = None
TOKEN_LOG: list[dict] = []


def _openai_client() -> OpenAI:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = OpenAI()
    return _CLIENT


def _record_usage(model: str, kind: str, resp) -> None:
    if os.getenv("TRACK_TOKENS"):
        u = getattr(resp, "usage", None)
        if u is None:
            return
        TOKEN_LOG.append({
            "model": model,
            "kind": kind,
            "prompt_tokens": u.prompt_tokens,
            "completion_tokens": u.completion_tokens,
            "total_tokens": u.total_tokens,
        })


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
    _record_usage(model, "vision", resp)
    return resp.choices[0].message.content


def text_call(prompt: str, model: str = "gpt-4o", max_tokens: int = 8000) -> str:
    client = _openai_client()
    resp = client.chat.completions.create(
        model=model, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    _record_usage(model, "text", resp)
    return resp.choices[0].message.content
