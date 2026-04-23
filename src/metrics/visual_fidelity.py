"""
Visual Fidelity Metrics: 원본 디자인 이미지와 생성 결과의 시각적 유사도 측정.

1. Element-level SSIM: 카드 영역을 크롭해서 비교 (텍스트 영향 최소화)
2. VLM-as-Judge: GPT-4o가 원본 vs 생성물을 비교 채점
"""

import base64
import json
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image


def element_level_ssim(
    original_img: Image.Image,
    generated_img: Image.Image,
    card_positions: list[dict],
) -> dict:
    """카드 영역별로 크롭하여 SSIM 비교.

    텍스트가 없는 원본 디자인과 텍스트가 있는 생성물을 비교할 때,
    전체 이미지 SSIM은 텍스트 유무로 왜곡됨.
    카드 영역만 크롭하면 카드 스타일(글래스모피즘, 보더 등)의 유사도를 측정 가능.
    """
    from src.metrics.visual_similarity import compute_ssim

    orig_w, orig_h = original_img.size
    gen_w, gen_h = generated_img.size

    card_scores = []
    for card in card_positions:
        # 좌표를 픽셀로 변환
        x1 = int(card.get("x1", card.get("left", 0) / 100) * orig_w)
        y1 = int(card.get("y1", card.get("top", 0) / 100) * orig_h)
        x2 = int(card.get("x2", (card.get("left", 0) + card.get("width", 20)) / 100) * orig_w)
        y2 = int(card.get("y2", (card.get("top", 0) + card.get("height", 40)) / 100) * orig_h)

        # 크롭
        orig_crop = original_img.crop((x1, y1, x2, y2))
        # 생성물은 1280x720으로 렌더링됨
        gx1 = int(x1 * gen_w / orig_w)
        gy1 = int(y1 * gen_h / orig_h)
        gx2 = int(x2 * gen_w / orig_w)
        gy2 = int(y2 * gen_h / orig_h)
        gen_crop = generated_img.crop((gx1, gy1, gx2, gy2))

        # 같은 크기로 리사이즈
        size = (200, 200)
        orig_resized = orig_crop.resize(size)
        gen_resized = gen_crop.resize(size)

        ssim = compute_ssim(orig_resized, gen_resized)
        card_scores.append(ssim)

    # 전체 이미지 SSIM도 계산
    full_ssim = compute_ssim(original_img, generated_img)

    return {
        "element_ssim": round(np.mean(card_scores), 4) if card_scores else 0,
        "full_ssim": full_ssim,
        "card_scores": [round(s, 4) for s in card_scores],
        "num_cards": len(card_scores),
    }


def vlm_judge(
    original_b64: str,
    generated_b64: str,
    model: str = "claude-4.6-opus",
) -> dict:
    """VLM-as-Judge: Claude 4.6 Opus가 원본 디자인 vs 생성 결과를 비교 채점.

    생성 모델(GPT-4o)과 다른 모델로 평가하여 bias를 줄임.
    """
    import os
    import boto3

    prompt = """두 이미지를 비교하세요.
첫 번째 이미지는 원본 디자인이고, 두 번째는 이를 HTML/CSS로 변환한 결과를 렌더링한 것입니다.

★ 엄격하게 채점하세요. 7~10점은 정말 비슷할 때만 주세요.

다음 5가지 기준으로 1~10점 채점하세요:

1. **레이아웃 구조** (Layout): 원본의 배치 패턴을 따르는가? 예: 원본이 방사형(hub-spoke)이면 생성물도 방사형이어야 하고, 그리드로 바꿨으면 1~3점. 원본이 타임라인이면 수평 나열이어야 하고 세로로 쌓았으면 1~3점. **배치 패턴이 같은지가 핵심**. 미적 완성도가 아니라 구조적 패턴의 일치를 평가하세요.
2. **카드 재질** (Material): 카드가 글래스모피즘(반투명+blur)인가, 단색 블록인가? 네온 글로우 보더가 있는가? 원본과 같은 재질감이면 높은 점수.
3. **배경 효과** (Background): 배경의 그라디언트, 글로우, 패턴(도트/그리드/회로선), 장식 요소가 원본과 비슷한가? 단색 배경이면 낮은 점수.
4. **색상 팔레트** (Color): 원본의 주요 색상(시안, 보라, 네온 등)을 유지하는가? 색조가 비슷한가?
5. **전체 인상** (Overall): 두 이미지를 나란히 놓았을 때 "같은 디자인"으로 보이는가? 1점=완전히 다름, 10점=거의 동일.

JSON으로만 응답:
{"layout": N, "material": N, "background": N, "color": N, "overall": N}"""

    # Claude 4.6 Opus via Bedrock Converse API
    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=os.getenv("AWS_REGION", "us-west-2"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )

    orig_bytes = base64.b64decode(original_b64)
    gen_bytes = base64.b64decode(generated_b64)
    orig_fmt = "jpeg" if orig_bytes[:2] == b'\xff\xd8' else "png"
    gen_fmt = "jpeg" if gen_bytes[:2] == b'\xff\xd8' else "png"

    model_id = os.getenv("BEDROCK_CLAUDE_OPUS_MODEL_ID", "us.anthropic.claude-opus-4-6-v1")

    resp = bedrock.converse(
        modelId=model_id,
        messages=[{
            "role": "user",
            "content": [
                {"image": {"format": orig_fmt, "source": {"bytes": orig_bytes}}},
                {"image": {"format": gen_fmt, "source": {"bytes": gen_bytes}}},
                {"text": prompt},
            ],
        }],
        inferenceConfig={"maxTokens": 300},
    )

    raw = resp["output"]["message"]["content"][0]["text"]
    import re
    json_match = re.search(r'\{[^}]+\}', raw)
    if json_match:
        try:
            scores = json.loads(json_match.group(0))
            return {
                "layout": scores.get("layout", 0),
                "material": scores.get("material", 0),
                "background": scores.get("background", 0),
                "color": scores.get("color", 0),
                "overall": scores.get("overall", 0),
            }
        except:
            pass
    return {"layout": 0, "material": 0, "background": 0, "color": 0, "overall": 0}
