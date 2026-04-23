"""
Metric 1: Background Preservation Score (BPS)
배경 복잡도가 보존되었는지 측정. VLM 없이 완전 자동.

원본이 복잡한 배경(그라디언트, 이미지, 패턴)이었는데
생성 결과가 단색 배경이면 → loss.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

# 배경색 판정 임계값 — 이 이하면 "단색 배경"으로 간주
SOLID_BG_THRESHOLD = 15.0


def sample_background_pixels(image: Image.Image, n_samples: int = 100) -> np.ndarray:
    """이미지의 가장자리(배경 영역)에서 픽셀 샘플링.

    슬라이드에서 가장자리는 보통 배경 영역이므로,
    여기서 색상 분산이 높으면 복잡한 배경.
    """
    img = np.array(image.convert("RGB"))
    h, w = img.shape[:2]

    pixels = []

    # 상단 가장자리
    for x in np.linspace(0, w - 1, n_samples // 5, dtype=int):
        pixels.append(img[2, x])
    # 하단 가장자리
    for x in np.linspace(0, w - 1, n_samples // 5, dtype=int):
        pixels.append(img[h - 3, x])
    # 좌측 가장자리
    for y in np.linspace(0, h - 1, n_samples // 5, dtype=int):
        pixels.append(img[y, 2])
    # 우측 가장자리
    for y in np.linspace(0, h - 1, n_samples // 5, dtype=int):
        pixels.append(img[y, w - 3])
    # 네 모서리 영역 (10x10)
    for corner in [(5, 5), (5, w - 5), (h - 5, 5), (h - 5, w - 5)]:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                y, x = corner[0] + dy, corner[1] + dx
                if 0 <= y < h and 0 <= x < w:
                    pixels.append(img[y, x])

    return np.array(pixels[:n_samples])


def compute_color_variance(pixels: np.ndarray) -> float:
    """픽셀 배열의 색상 분산 계산.

    RGB 각 채널의 표준편차를 평균하여 단일 값으로.
    """
    if len(pixels) == 0:
        return 0.0
    return float(np.mean(np.std(pixels.astype(float), axis=0)))


def background_preservation_score(
    original: Image.Image,
    generated: Image.Image,
) -> dict:
    """Background Preservation Score 계산.

    Returns:
        dict with:
        - score: 0.0 ~ 1.0 (1.0 = 완벽 보존)
        - original_variance: 원본 배경 색상 분산
        - generated_variance: 생성 결과 배경 색상 분산
        - original_is_complex: 원본이 복잡한 배경인지
        - loss_detected: 손실이 감지되었는지
    """
    orig_pixels = sample_background_pixels(original)
    gen_pixels = sample_background_pixels(generated)

    orig_var = compute_color_variance(orig_pixels)
    gen_var = compute_color_variance(gen_pixels)

    orig_complex = orig_var > SOLID_BG_THRESHOLD

    if not orig_complex:
        # 원본이 단색 → 손실 가능성 없음
        score = 1.0
        loss = False
    else:
        # 원본이 복잡 → 생성도 복잡해야 함
        if gen_var > SOLID_BG_THRESHOLD:
            # 둘 다 복잡 → 보존 정도에 따라 점수
            score = min(1.0, gen_var / orig_var)
        else:
            # 원본 복잡, 생성 단색 → 명확한 loss
            score = gen_var / orig_var
        loss = gen_var < orig_var * 0.5  # 50% 이상 감소하면 loss

    return {
        "score": round(score, 4),
        "original_variance": round(orig_var, 2),
        "generated_variance": round(gen_var, 2),
        "original_is_complex": orig_complex,
        "loss_detected": loss,
    }
