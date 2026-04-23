"""
기존 메트릭: CLIP Score + SSIM
Design2Code, SlideCoder와 비교 가능하도록 동일 메트릭 구현.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def compute_ssim(img1: Image.Image, img2: Image.Image) -> float:
    """SSIM (Structural Similarity Index) 계산."""
    try:
        from skimage.metrics import structural_similarity
    except ImportError:
        # skimage 없으면 간이 계산
        a = np.array(img1.resize((640, 360)).convert("RGB")).astype(float)
        b = np.array(img2.resize((640, 360)).convert("RGB")).astype(float)
        mse = np.mean((a - b) ** 2)
        if mse == 0:
            return 1.0
        return round(float(1.0 - mse / (255.0 ** 2)), 4)

    size = (640, 360)
    a = np.array(img1.resize(size).convert("RGB"))
    b = np.array(img2.resize(size).convert("RGB"))
    return round(float(structural_similarity(a, b, channel_axis=2, data_range=255)), 4)


def compute_clip_score(img1: Image.Image, img2: Image.Image) -> float:
    """CLIP Score — 두 이미지 간 의미적 유사도."""
    try:
        import torch
        from transformers import CLIPProcessor, CLIPModel
    except ImportError:
        return 0.0

    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

    inputs = processor(images=[img1, img2], return_tensors="pt", padding=True)
    with torch.no_grad():
        pixel_values = inputs["pixel_values"]
        vision_outputs = model.vision_model(pixel_values=pixel_values)
        features = vision_outputs.pooler_output
        features = model.visual_projection(features)
        features = features / features.norm(dim=-1, keepdim=True)
        similarity = (features[0] @ features[1]).item()

    return round(similarity, 4)
