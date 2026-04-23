"""구조 메트릭: Block-Match, element-IoU, CLIP similarity, SSIM.

RQ3(측정 타당성) 검증을 위해 '기존 D2C 메트릭'을 구현한다.
이들과 VLM-judge의 τ 상관이 낮음을 보이는 것이 RQ3의 증거.
"""
from __future__ import annotations

from typing import Any


def block_match(ref_blocks: list[dict], gen_blocks: list[dict]) -> float:
    """Design2Code-style block match.

    ref/gen 블록을 (x, y, w, h, tag) 형태로 받아 IoU 기반 매칭 후 F1 반환.
    """
    if not ref_blocks or not gen_blocks:
        return 0.0
    matched = 0
    for rb in ref_blocks:
        best_iou = 0.0
        for gb in gen_blocks:
            best_iou = max(best_iou, _bbox_iou(rb, gb))
        if best_iou >= 0.5:
            matched += 1
    precision = matched / max(len(gen_blocks), 1)
    recall = matched / max(len(ref_blocks), 1)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def element_iou(ref_blocks: list[dict], gen_blocks: list[dict]) -> float:
    """요소 단위 평균 IoU (SlidesBench 스타일)."""
    if not ref_blocks or not gen_blocks:
        return 0.0
    ious = []
    for rb in ref_blocks:
        best = 0.0
        for gb in gen_blocks:
            best = max(best, _bbox_iou(rb, gb))
        ious.append(best)
    return sum(ious) / len(ious)


def _bbox_iou(a: dict, b: dict) -> float:
    ax1, ay1, ax2, ay2 = a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"]
    bx1, by1, bx2, by2 = b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def clip_similarity(img_a_path: str, img_b_path: str, model_cache: Any = None) -> float:
    """CLIP embedding cosine similarity. 본 함수는 lazy import."""
    try:
        from PIL import Image
        import torch
        from transformers import CLIPModel, CLIPProcessor
    except ImportError as e:
        raise ImportError(f"CLIP 의존성 필요: pip install transformers torch pillow ({e})")

    if model_cache is None:
        model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    else:
        model, proc = model_cache

    a = Image.open(img_a_path).convert("RGB")
    b = Image.open(img_b_path).convert("RGB")
    inputs = proc(images=[a, b], return_tensors="pt")
    with torch.no_grad():
        feats = model.get_image_features(**inputs)
    feats = feats / feats.norm(dim=-1, keepdim=True)
    return float((feats[0] @ feats[1]).item())


def ssim_similarity(img_a_path: str, img_b_path: str) -> float:
    """SSIM — 두 이미지 크기를 맞춘 뒤 gray-scale SSIM."""
    try:
        from PIL import Image
        import numpy as np
        from skimage.metrics import structural_similarity
    except ImportError as e:
        raise ImportError(f"SSIM 의존성 필요: pip install scikit-image pillow numpy ({e})")

    a = Image.open(img_a_path).convert("L")
    b = Image.open(img_b_path).convert("L").resize(a.size)
    return float(structural_similarity(np.array(a), np.array(b)))
