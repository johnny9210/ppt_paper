"""결정론적 CV 추출기 — VLM이 측정하지 않는다. CV가 한다.

리뷰어 3명 합의:
- VLM이 "이 텍스트는 카드의 30%"같은 비율을 측정하게 하지 마라 (hallucinate)
- 대신 결정론적 CV로 진짜 값 추출 → 프롬프트에 FACT로 주입

제공 함수:
- extract_palette_hex: k-means 기반 지배색 hex (N=5)
- saturation_stats: HSV 채도/명도 통계
- text_box_heights: OCR 기반 텍스트 픽셀 높이 + 바운딩박스
- visual_facts: 위 세 가지를 한 번에
"""
from __future__ import annotations

import base64
import re
from io import BytesIO

import numpy as np
from PIL import Image


# ────────────────────────────────────────────
# 이미지 로딩 / crop
# ────────────────────────────────────────────

def _load_image(image_b64: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(image_b64))).convert("RGB")


def _crop_by_bbox(img: Image.Image, bbox_ratio: tuple[float, float, float, float]) -> Image.Image:
    W, H = img.size
    x1 = max(0, int(bbox_ratio[0] * W))
    y1 = max(0, int(bbox_ratio[1] * H))
    x2 = min(W, int(bbox_ratio[2] * W))
    y2 = min(H, int(bbox_ratio[3] * H))
    return img.crop((x1, y1, x2, y2))


# ────────────────────────────────────────────
# 1) Palette — k-means 지배색 추출
# ────────────────────────────────────────────

def extract_palette_hex(
    image_b64: str,
    bbox_ratio: tuple[float, float, float, float] | None = None,
    n_colors: int = 5,
) -> list[dict]:
    """이 영역의 지배색 N개를 hex + 점유율로 반환.

    Returns:
        [{"hex": "#D4AF37", "pct": 0.35, "role_guess": "accent"}, ...]
    """
    from sklearn.cluster import KMeans

    img = _load_image(image_b64)
    if bbox_ratio:
        img = _crop_by_bbox(img, bbox_ratio)

    # 다운샘플해서 속도 ↑
    img = img.resize((min(img.width, 160), min(img.height, 160)))
    arr = np.array(img).reshape(-1, 3)

    # 극단 픽셀(순흑/순백) 제거하면 "실제 UI 색" 추출이 더 정확
    mask = ~(
        ((arr[:, 0] < 10) & (arr[:, 1] < 10) & (arr[:, 2] < 10))  # 순흑 제외하지 말기 — 실제 네이비와 구분 애매
        | ((arr[:, 0] > 250) & (arr[:, 1] > 250) & (arr[:, 2] > 250))  # 순백 제외 (텍스트 과대평가 방지)
    )
    if mask.sum() > n_colors * 10:
        arr = arr[mask]

    km = KMeans(n_clusters=n_colors, n_init="auto", random_state=0).fit(arr)
    centers = km.cluster_centers_.astype(int)
    labels = km.labels_
    counts = np.bincount(labels, minlength=n_colors)
    total = counts.sum()

    order = np.argsort(-counts)
    palette: list[dict] = []
    for i in order:
        r, g, b = centers[i]
        pct = float(counts[i] / total)
        palette.append({
            "hex": f"#{r:02X}{g:02X}{b:02X}",
            "rgb": [int(r), int(g), int(b)],
            "pct": round(pct, 3),
        })

    # role heuristic: 어두운 색=bg, 밝고 채도 높은 색=accent
    for p in palette:
        r, g, b = p["rgb"]
        brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        max_c, min_c = max(r, g, b) / 255, min(r, g, b) / 255
        sat = 0 if max_c == 0 else (max_c - min_c) / max_c
        if brightness < 0.2:
            p["role_guess"] = "bg_primary"
        elif brightness < 0.45:
            p["role_guess"] = "bg_secondary"
        elif sat > 0.4:
            p["role_guess"] = "accent"
        elif brightness > 0.85:
            p["role_guess"] = "text_bright"
        else:
            p["role_guess"] = "mid_neutral"

    return palette


# ────────────────────────────────────────────
# 2) HSV 통계 — 채도·명도 분포
# ────────────────────────────────────────────

def saturation_stats(image_b64: str, bbox_ratio: tuple[float, float, float, float] | None = None) -> dict:
    """영역의 HSV 통계 — accent 채도가 얼마나 강한지 등 판단용."""
    img = _load_image(image_b64)
    if bbox_ratio:
        img = _crop_by_bbox(img, bbox_ratio)
    img_hsv = np.array(img.convert("HSV"))
    H = img_hsv[..., 0].astype(np.float32)
    S = img_hsv[..., 1].astype(np.float32) / 255.0
    V = img_hsv[..., 2].astype(np.float32) / 255.0

    # high saturation 영역 (S>0.5) — 강조 픽셀의 평균 hue
    high_sat_mask = S > 0.5
    if high_sat_mask.sum() > 50:
        accent_hue = float(H[high_sat_mask].mean())
    else:
        accent_hue = float(H.mean())

    return {
        "saturation_mean": round(float(S.mean()), 3),
        "saturation_p90": round(float(np.percentile(S, 90)), 3),
        "saturation_p99": round(float(np.percentile(S, 99)), 3),
        "brightness_mean": round(float(V.mean()), 3),
        "brightness_p10": round(float(np.percentile(V, 10)), 3),
        "brightness_p90": round(float(np.percentile(V, 90)), 3),
        "accent_hue_estimate": round(accent_hue, 1),  # OpenCV HSV hue 0~255 (PIL)
        "high_saturation_coverage": round(float(high_sat_mask.mean()), 3),
    }


# ────────────────────────────────────────────
# 3) OCR 기반 텍스트 픽셀 높이
# ────────────────────────────────────────────

def text_box_heights(
    image_b64: str,
    bbox_ratio: tuple[float, float, float, float] | None = None,
    min_conf: int = 30,
) -> list[dict]:
    """Tesseract로 텍스트 감지 후 실제 픽셀 높이 반환 (큰 것 → 작은 것 순)."""
    try:
        import pytesseract
    except ImportError:
        return []

    img = _load_image(image_b64)
    if bbox_ratio:
        img = _crop_by_bbox(img, bbox_ratio)

    # OCR
    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, lang="eng+kor")
    except Exception:
        try:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        except Exception:
            return []

    results: list[dict] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = int(data["conf"][i])
        except Exception:
            conf = 0
        if conf < min_conf:
            continue
        h = int(data["height"][i])
        w = int(data["width"][i])
        x = int(data["left"][i])
        y = int(data["top"][i])
        if h < 6 or w < 6:
            continue
        results.append({
            "text": text,
            "height_px": h,
            "width_px": w,
            "x": x, "y": y,
            "conf": conf,
        })

    # 큰 것부터 정렬
    results.sort(key=lambda r: -r["height_px"])
    return results[:10]


# ────────────────────────────────────────────
# 4) 한 번에 묶어주는 API
# ────────────────────────────────────────────

def visual_facts(
    image_b64: str,
    bbox_ratio: tuple[float, float, float, float] | None = None,
    n_palette: int = 5,
) -> dict:
    """bbox 영역에 대한 모든 결정론적 시각 사실을 한 번에 뽑는다.

    이 결과를 그대로 프롬프트에 FACT로 주입하면 VLM이 추측 대신 관측값 사용.
    """
    return {
        "palette": extract_palette_hex(image_b64, bbox_ratio, n_colors=n_palette),
        "hsv": saturation_stats(image_b64, bbox_ratio),
        "text_heights": text_box_heights(image_b64, bbox_ratio),
        "bbox_ratio": list(bbox_ratio) if bbox_ratio else None,
    }


def format_facts_as_prompt(facts: dict) -> str:
    """facts → 사람/모델이 읽기 좋은 마크다운."""
    lines: list[str] = ["**이 영역의 결정론적 시각 측정값** (CV 도구로 추출, 추측 아님):"]

    lines.append("\n*지배 팔레트 (k-means)*:")
    for p in facts["palette"]:
        lines.append(f"- `{p['hex']}` ({int(p['pct'] * 100)}%, role 추정: {p['role_guess']})")

    hsv = facts["hsv"]
    lines.append("\n*채도·명도 통계*:")
    lines.append(
        f"- 채도 mean={hsv['saturation_mean']}, p90={hsv['saturation_p90']} "
        f"(강조 픽셀의 채도는 전형적으로 p90 수치)"
    )
    lines.append(
        f"- 명도 mean={hsv['brightness_mean']}, p10={hsv['brightness_p10']} (bg), p90={hsv['brightness_p90']} (highlight)"
    )
    lines.append(f"- 고채도 영역 점유율: {int(hsv['high_saturation_coverage']*100)}%")

    if facts["text_heights"]:
        lines.append("\n*OCR 감지 텍스트의 실제 픽셀 높이* (큰 순):")
        for t in facts["text_heights"]:
            lines.append(f"- \"{t['text']}\" → **{t['height_px']}px** (높이), width={t['width_px']}px, conf={t['conf']}")
        lines.append(
            "\n★ 반드시 위 픽셀 높이에 비례하는 CSS `font-size` 사용. "
            "예: 큰 값이 80px면 `font-size: 5rem (~80px)`, 작은 라벨이 20px면 `font-size: 1.25rem (~20px)`."
        )
    else:
        lines.append("\n*OCR 감지 실패* — 텍스트 추출 정보 없음 (이미지에서 직접 관찰 필요)")

    return "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys
    from final_test.methods._common import b64_image  # type: ignore

    sid = sys.argv[1] if len(sys.argv) > 1 else "design_10_stats_hero"
    b64 = b64_image(sid)

    # 전체 영역
    facts = visual_facts(b64)
    print("=" * 60)
    print(f"WHOLE SLIDE ({sid})")
    print("=" * 60)
    print(format_facts_as_prompt(facts))

    # Hero 영역 (stats_hero 기준)
    print("\n" + "=" * 60)
    print("HERO bbox (대략 0.05~0.45, 0.12~0.88)")
    print("=" * 60)
    hero_facts = visual_facts(b64, bbox_ratio=(0.05, 0.12, 0.45, 0.88))
    print(format_facts_as_prompt(hero_facts))
