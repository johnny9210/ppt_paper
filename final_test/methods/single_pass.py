"""Single-pass VLM baseline.

한 번의 VLM 호출로 전체 슬라이드 HTML/CSS를 생성. GPT-4o, GPT-5.4, Claude 공통.
"""
from __future__ import annotations

from typing import Callable


BASE_PROMPT = """You are an expert web designer.
Given the design image, produce a COMPLETE standalone HTML document that visually reproduces the design as closely as possible.

Requirements:
- Use modern CSS (glassmorphism, neon glow, gradients, backdrop-filter, box-shadow with rgba) where appropriate.
- Include ALL text content shown in the design.
- Output only the HTML (no markdown fences, no commentary).
"""


def generate(call_vision_fn: Callable[[str, str, int], str], image_b64: str, max_tokens: int = 12000) -> str:
    """단일 패스 생성."""
    return call_vision_fn(image_b64, BASE_PROMPT, max_tokens)


def generate_with_content(
    call_vision_fn: Callable[[str, str, int], str],
    image_b64: str,
    content_json: str,
    max_tokens: int = 12000,
) -> str:
    """콘텐츠 텍스트를 함께 제공 (공정 비교용)."""
    prompt = BASE_PROMPT + f"\n\nContent to include (JSON):\n```json\n{content_json}\n```"
    return call_vision_fn(image_b64, prompt, max_tokens)
