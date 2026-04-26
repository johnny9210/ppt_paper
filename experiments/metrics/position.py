"""Position alignment metric — Design2Code (NAACL 2025) style.

For each matched (reference, generated) text block, compute the L2 distance
between their centers normalized to [0,1] of the image diagonal. The metric
is the average normalized distance across all matched pairs, inverted so
higher = better alignment.

Specifically:
    Position = mean over matched pairs of: 1 - (d / D)
    where d = L2(center_ref, center_gen), D = sqrt(W² + H²)

Matching uses the same IoU-based pairing as Block-Match (≥ 0.5 IoU). Blocks
that have no match contribute 0 to the average (penalizing missing or
hallucinated elements).
"""
from __future__ import annotations

import math


def _bbox_iou(a: dict, b: dict) -> float:
    ax1, ay1, ax2, ay2 = a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"]
    bx1, by1, bx2, by2 = b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def _center(b: dict) -> tuple[float, float]:
    return (b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)


def position_alignment(
    ref_blocks: list[dict],
    gen_blocks: list[dict],
    image_width: int,
    image_height: int,
    iou_thresh: float = 0.5,
) -> float:
    """Mean (1 - d/D) over reference blocks.

    Args:
        ref_blocks, gen_blocks: from ocr_blocks.extract_blocks()
        image_width, image_height: image dimensions in px
        iou_thresh: minimum IoU to consider a block matched (Design2Code uses 0.5)

    Returns:
        Score in [0, 1]. 1.0 = perfect alignment for every reference block.
        Unmatched reference blocks contribute 0 to the mean.
    """
    if not ref_blocks:
        return 0.0
    diagonal = math.sqrt(image_width ** 2 + image_height ** 2)
    scores: list[float] = []
    for rb in ref_blocks:
        best_iou = 0.0
        best_match: dict | None = None
        for gb in gen_blocks:
            iou = _bbox_iou(rb, gb)
            if iou > best_iou:
                best_iou = iou
                best_match = gb
        if best_match is None or best_iou < iou_thresh:
            scores.append(0.0)
            continue
        rx, ry = _center(rb)
        gx, gy = _center(best_match)
        d = math.sqrt((rx - gx) ** 2 + (ry - gy) ** 2)
        scores.append(max(0.0, 1.0 - d / diagonal))
    return sum(scores) / len(scores)
