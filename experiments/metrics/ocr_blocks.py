"""OCR-based text-block extraction — feeds Block-Match and Position metrics.

For each input image (PNG of a slide, either reference or rendered output),
returns a list of detected text blocks:
    [{"x": int, "y": int, "w": int, "h": int, "text": str, "conf": float}, ...]

Coordinates are in pixels. Block-Match and Position metrics consume the same
schema for both reference and generated images, so blocks must be extracted
identically on both sides.
"""
from __future__ import annotations

from pathlib import Path

import pytesseract
from PIL import Image


def extract_blocks(image_path: str | Path, min_conf: float = 50.0,
                   min_area: int = 200) -> list[dict]:
    """Tesseract OCR → list of text-block dicts.

    Args:
        image_path: PNG/JPG to OCR.
        min_conf:   discard tokens below this confidence (0-100).
        min_area:   discard boxes smaller than this many pixels (noise).

    Returns:
        List of {x, y, w, h, text, conf} sorted by reading order (top-down,
        left-to-right by line).
    """
    img = Image.open(image_path).convert("RGB")
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    blocks: list[dict] = []
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except Exception:
            continue
        if conf < min_conf:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        if w * h < min_area:
            continue
        blocks.append({
            "x": int(x), "y": int(y), "w": int(w), "h": int(h),
            "text": text, "conf": conf,
        })

    # Group adjacent tokens on the same line into compound blocks
    blocks = _group_words_to_lines(blocks)
    return blocks


def _group_words_to_lines(words: list[dict], y_tolerance_ratio: float = 0.5) -> list[dict]:
    """Group word-level OCR detections into line-level blocks.

    Two words are on the same line if their y-centers are within
    `y_tolerance_ratio * max(h_a, h_b)` of each other.
    """
    if not words:
        return []
    # Sort by y, then x
    words = sorted(words, key=lambda b: (b["y"], b["x"]))
    lines: list[list[dict]] = []
    for w in words:
        placed = False
        for line in lines:
            ly = sum((b["y"] + b["h"] / 2) for b in line) / len(line)
            wy = w["y"] + w["h"] / 2
            tol = y_tolerance_ratio * max(w["h"], max(b["h"] for b in line))
            if abs(ly - wy) <= tol:
                line.append(w)
                placed = True
                break
        if not placed:
            lines.append([w])

    merged: list[dict] = []
    for line in lines:
        line.sort(key=lambda b: b["x"])
        x = min(b["x"] for b in line)
        y = min(b["y"] for b in line)
        x2 = max(b["x"] + b["w"] for b in line)
        y2 = max(b["y"] + b["h"] for b in line)
        text = " ".join(b["text"] for b in line)
        conf = sum(b["conf"] for b in line) / len(line)
        merged.append({"x": x, "y": y, "w": x2 - x, "h": y2 - y,
                       "text": text, "conf": conf})
    return merged
