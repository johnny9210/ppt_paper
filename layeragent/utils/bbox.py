"""DCGen-style bbox overlay: 전체 이미지 보존하면서 특정 영역만 빨간 사각형으로 하이라이트.

Key insight from DCGen (FSE 2025, arxiv:2406.16386):
- 크롭하면 global context (palette, composition, other elements) 소실
- 대신 전체 이미지 + 빨간 bbox overlay 사용하면 MLLM이 glocal context 보면서 해당 영역 설명
"""
from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image, ImageDraw


def draw_bbox_on_image(
    image_b64: str,
    bbox_ratio: tuple[float, float, float, float],
    color: tuple[int, int, int] = (255, 0, 0),
    width: int = 6,
    label: str | None = None,
) -> str:
    """이미지에 빨간 bbox 사각형을 그려 base64로 반환.

    Args:
        image_b64: base64 encoded image
        bbox_ratio: (x1, y1, x2, y2) in ratio 0~1 of image size
        color: RGB tuple (default red)
        width: stroke width in pixels
        label: optional text label above the bbox

    Returns:
        base64 encoded PNG with overlay
    """
    img_bytes = base64.b64decode(image_b64)
    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    W, H = img.size

    x1 = max(0, int(bbox_ratio[0] * W))
    y1 = max(0, int(bbox_ratio[1] * H))
    x2 = min(W, int(bbox_ratio[2] * W))
    y2 = min(H, int(bbox_ratio[3] * H))

    draw = ImageDraw.Draw(img, "RGBA")
    # 외곽 빨간 사각형
    for offset in range(width):
        draw.rectangle([x1 - offset, y1 - offset, x2 + offset, y2 + offset], outline=color + (255,))
    # 반투명 빨간 채움 (영역 강조)
    draw.rectangle([x1, y1, x2, y2], fill=color + (30,))

    if label:
        try:
            from PIL import ImageFont
            font = ImageFont.load_default()
            draw.text((x1 + 8, max(0, y1 - 20)), label, fill=color, font=font)
        except Exception:
            pass

    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def draw_multiple_bboxes(
    image_b64: str,
    bboxes: list[dict],
) -> str:
    """여러 bbox를 한 이미지에 그림 (색깔로 구분).

    bboxes: [{"bbox": (x1,y1,x2,y2), "label": "card_1", "color": (255,0,0)}, ...]
    """
    img_bytes = base64.b64decode(image_b64)
    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    W, H = img.size
    draw = ImageDraw.Draw(img, "RGBA")
    try:
        from PIL import ImageFont
        font = ImageFont.load_default()
    except Exception:
        font = None

    for i, bb in enumerate(bboxes):
        color = bb.get("color", (255, 0, 0))
        bbox = bb["bbox"]
        x1 = max(0, int(bbox[0] * W)); y1 = max(0, int(bbox[1] * H))
        x2 = min(W, int(bbox[2] * W)); y2 = min(H, int(bbox[3] * H))
        for offset in range(4):
            draw.rectangle([x1 - offset, y1 - offset, x2 + offset, y2 + offset], outline=color + (255,))
        if label := bb.get("label"):
            draw.text((x1 + 4, max(0, y1 - 16)), label, fill=color, font=font)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
