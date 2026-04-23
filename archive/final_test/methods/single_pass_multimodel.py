"""Single-pass baseline that supports multiple model backends (RQ4 / SOTA 일관성).

Backends:
- 'gpt-4o' → OpenAI direct
- 'gpt-5.4' → Azure OpenAI (env: APIM_AOAI_*, GPT_MODEL)
- 'claude-4.6-opus' → AWS Bedrock (env: AWS_*, BEDROCK_CLAUDE_OPUS_MODEL_ID)
"""
from __future__ import annotations

import base64
import json
import os
import re

from . import _common


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


def _filter_content(content: dict) -> dict:
    skip = {"speaker_script", "infographic_script"}
    return {k: v for k, v in content.items() if k not in skip}


def _call_gpt4o(image_b64: str, prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8000,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            {"type": "text", "text": prompt},
        ]}],
    )
    return resp.choices[0].message.content


def _call_gpt54_azure(image_b64: str, prompt: str) -> str:
    from openai import AzureOpenAI
    client = AzureOpenAI(
        azure_endpoint=os.getenv("APIM_AOAI_ENDPOINT"),
        api_key=os.getenv("APIM_AOAI_API_KEY"),
        api_version=os.getenv("GPT_API_VERSION", "2025-04-01-preview"),
    )
    model = os.getenv("GPT_MODEL", "gpt-5.4")
    resp = client.chat.completions.create(
        model=model,
        max_completion_tokens=8000,  # GPT-5.x uses max_completion_tokens
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            {"type": "text", "text": prompt},
        ]}],
    )
    return resp.choices[0].message.content


def _detect_image_format(img_bytes: bytes) -> str:
    """파일 헤더로 실제 이미지 포맷 판별 (확장자 무시)."""
    if img_bytes[:4] == b"\x89PNG":
        return "png"
    if img_bytes[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if img_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
        return "webp"
    return "png"  # default fallback


def _call_claude_bedrock(image_b64: str, prompt: str, opus: bool = True) -> str:
    import boto3
    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=os.getenv("AWS_REGION", "us-west-2"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
    model_id = os.getenv("BEDROCK_CLAUDE_OPUS_MODEL_ID" if opus else "BEDROCK_CLAUDE_SONNET_MODEL_ID")
    img_bytes = base64.b64decode(image_b64)
    img_format = _detect_image_format(img_bytes)
    resp = bedrock.converse(
        modelId=model_id,
        messages=[{
            "role": "user",
            "content": [
                {"image": {"format": "png" if img_format == "png" else img_format, "source": {"bytes": img_bytes}}},
                {"text": prompt},
            ],
        }],
        inferenceConfig={"maxTokens": 8000},
    )
    return resp["output"]["message"]["content"][0]["text"]


def run(slide_id: str, seed: int = 0, model: str = "gpt-4o") -> str:
    meta = _common.load_meta()
    design = _common.get_design_by_id(meta, slide_id)
    image_b64 = _common.b64_image(slide_id)
    content_json = json.dumps(_filter_content(design["content"]), ensure_ascii=False, indent=2)
    prompt = PROMPT_WITH_CONTENT.format(content_json=content_json)

    if model == "gpt-4o":
        raw = _call_gpt4o(image_b64, prompt)
    elif model in ("gpt-5.4", "gpt-5"):
        raw = _call_gpt54_azure(image_b64, prompt)
    elif model in ("claude-4.6-opus", "claude-opus", "claude"):
        raw = _call_claude_bedrock(image_b64, prompt, opus=True)
    elif model in ("claude-4.5-sonnet", "claude-sonnet"):
        raw = _call_claude_bedrock(image_b64, prompt, opus=False)
    else:
        raise ValueError(f"Unknown model: {model}")

    return _common.extract_html(raw)
