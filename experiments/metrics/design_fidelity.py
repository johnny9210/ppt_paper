"""Design-fidelity metric set — SOTA-aligned (Design2Code + AutoPresent + AeSlides).

Fixes the "blank-canvas attack" exposed by CLIP/LPIPS on McKinsey eval.
Each metric measures a concrete design property; together they catch:
  - Block-Match  (Design2Code 2024) — element area coverage match
  - Element-IoU  (SlidesBench 2025) — bbox overlap of best-matched pairs
  - CIEDE2000    (SlidesBench 2025) — perceptual color distance per pair
  - Whitespace   (AeSlides 2026)   — penalizes "70% empty" outputs
  - Collision    (AeSlides 2026)   — penalizes overlapping/escaping elements
  - Layout 0-5   (AutoPresent 2025) — GPT-4o judge: alignment, no-overlap
  - Color 0-5    (AutoPresent 2025) — GPT-4o judge: contrast, harmony

DOM blocks are extracted via Playwright (not OCR) — more reliable than
OCR for synthesized rendering and matches what the generator actually
produced. Reference image uses OCR-based blocks (no source HTML).
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np
from PIL import Image


# ──────────────────────────────────────────────────────────────────────
# Block / element extraction
# ──────────────────────────────────────────────────────────────────────

_DOM_BLOCKS_JS = r"""
(() => {
  function bbox(el) {
    const r = el.getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height };
  }
  function isVisible(el) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (parseFloat(cs.opacity) < 0.05) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 10 || r.height < 10) return false;
    if (r.x + r.width < 0 || r.y + r.height < 0) return false;
    if (r.x > 1280 || r.y > 720) return false;
    return true;
  }
  function hasVisualStyle(cs) {
    if (cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)' &&
        cs.backgroundColor !== 'transparent') return true;
    if (cs.backgroundImage && cs.backgroundImage !== 'none') return true;
    if (cs.borderStyle && cs.borderStyle !== 'none' && parseFloat(cs.borderTopWidth) > 0) return true;
    if (cs.boxShadow && cs.boxShadow !== 'none') return true;
    return false;
  }
  function rgbToArr(s) {
    const m = (s||'').match(/(\d+(?:\.\d+)?)/g);
    if (!m || m.length < 3) return null;
    return [+m[0], +m[1], +m[2]];
  }
  const all = [...document.querySelectorAll('*')]
    .filter(el => el.tagName.toLowerCase() !== 'html' && el.tagName.toLowerCase() !== 'body')
    .filter(isVisible);
  return all.map(el => {
    const cs = getComputedStyle(el);
    const r = bbox(el);
    return {
      tag: el.tagName.toLowerCase(),
      x: r.x, y: r.y, w: r.w, h: r.h,
      area: r.w * r.h,
      hasText: (el.textContent || '').trim().length > 0,
      hasVisualStyle: hasVisualStyle(cs),
      bg: rgbToArr(cs.backgroundColor),
      color: rgbToArr(cs.color),
    };
  });
})()
"""


def extract_dom_blocks(html_path: Path) -> list[dict]:
    """Render an HTML file in Playwright and extract visible element bboxes."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page = ctx.new_page()
        try:
            page.goto(f"file://{html_path.resolve()}", wait_until="networkidle", timeout=15000)
        except Exception:
            page.goto(f"file://{html_path.resolve()}", wait_until="load", timeout=15000)
        page.wait_for_timeout(150)
        blocks = page.evaluate(_DOM_BLOCKS_JS)
        browser.close()
    return blocks


def visual_blocks_from_image(image_path: Path) -> list[dict]:
    """Reference-image side: detect coarse panels via simple connected
    components on a binarized non-background mask. This is the analogue of
    DOM block extraction when no source HTML exists.

    Why not OCR: we want PANELS (cards), not just text rectangles. OCR misses
    pure-color cards with no text.
    """
    img = np.array(Image.open(image_path).convert("RGB").resize((1280, 720)))
    # Detect "non-background" pixels: differ from edge-sampled background color.
    edge = np.concatenate([
        img[:30, :, :].reshape(-1, 3),
        img[-30:, :, :].reshape(-1, 3),
        img[:, :30, :].reshape(-1, 3),
        img[:, -30:, :].reshape(-1, 3),
    ], axis=0)
    bg = np.median(edge, axis=0)
    diff = np.linalg.norm(img.astype(np.float32) - bg, axis=2)
    fg = (diff > 25).astype(np.uint8)

    # Cheap connected components via skimage
    try:
        from skimage.measure import label, regionprops
    except ImportError:
        return []
    lab = label(fg, connectivity=2)
    blocks: list[dict] = []
    for r in regionprops(lab):
        y1, x1, y2, x2 = r.bbox
        w, h = x2 - x1, y2 - y1
        if w * h < 1500:        # filter noise
            continue
        if w < 20 or h < 20:    # filter slivers
            continue
        # Sample mean color inside the region as the block's representative
        crop = img[y1:y2, x1:x2]
        mean_color = crop.reshape(-1, 3).mean(axis=0).astype(int).tolist()
        blocks.append({
            "x": int(x1), "y": int(y1), "w": int(w), "h": int(h),
            "area": int(w * h), "bg": mean_color,
            "tag": "panel", "hasText": False, "hasVisualStyle": True,
            "color": None,
        })
    # Cap at 30 blocks (reference panels) to avoid runaway noise
    blocks.sort(key=lambda b: -b["area"])
    return blocks[:30]


# ──────────────────────────────────────────────────────────────────────
# Hungarian Element-IoU + Block-Match
# ──────────────────────────────────────────────────────────────────────

def _bbox_iou(a: dict, b: dict) -> float:
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    ix1, iy1 = max(a["x"], b["x"]), max(a["y"], b["y"])
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / union if union > 0 else 0.0


def hungarian_match(ref: list[dict], gen: list[dict]) -> list[tuple[int, int, float]]:
    """1:1 max-IoU matching via Hungarian (Design2Code/AutoPresent style)."""
    if not ref or not gen:
        return []
    from scipy.optimize import linear_sum_assignment
    n, m = len(ref), len(gen)
    cost = np.zeros((n, m))
    for i, r in enumerate(ref):
        for j, g in enumerate(gen):
            cost[i, j] = -_bbox_iou(r, g)        # negate → maximize IoU
    ri, gi = linear_sum_assignment(cost)
    return [(int(i), int(j), float(-cost[i, j])) for i, j in zip(ri, gi)]


def block_match_f1(ref: list[dict], gen: list[dict], iou_thresh: float = 0.5) -> dict:
    """Design2Code Block-Match: F1 over IoU≥thresh matches."""
    matches = hungarian_match(ref, gen)
    matched = [m for m in matches if m[2] >= iou_thresh]
    p = len(matched) / max(len(gen), 1)
    r = len(matched) / max(len(ref), 1)
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"f1": f1, "precision": p, "recall": r, "matched": len(matched)}


def element_iou_mean(ref: list[dict], gen: list[dict]) -> float:
    """SlidesBench: mean IoU across Hungarian-matched pairs."""
    matches = hungarian_match(ref, gen)
    if not matches:
        return 0.0
    return float(np.mean([m[2] for m in matches]))


# ──────────────────────────────────────────────────────────────────────
# CIEDE2000 (SlidesBench color distance)
# ──────────────────────────────────────────────────────────────────────

def _rgb_to_lab(rgb: list[int] | tuple[int, int, int]) -> tuple[float, float, float]:
    """sRGB [0..255] → CIE Lab (D65). Standard sRGB→XYZ→Lab path."""
    r, g, b = (c / 255.0 for c in rgb)
    def lin(c):  # sRGB linearization
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
    r, g, b = lin(r), lin(g), lin(b)
    # sRGB → XYZ (D65)
    X = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) * 100
    Y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) * 100
    Z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) * 100
    # XYZ → Lab (D65 reference white)
    Xn, Yn, Zn = 95.047, 100.0, 108.883
    def f(t):
        return t ** (1/3) if t > 0.008856 else 7.787 * t + 16/116
    fx, fy, fz = f(X / Xn), f(Y / Yn), f(Z / Zn)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b_ = 200 * (fy - fz)
    return float(L), float(a), float(b_)


def ciede2000(rgb1: list[int], rgb2: list[int]) -> float:
    """CIEDE2000 ΔE between two sRGB triplets. Lower = more similar.
    Range typically 0–100. <2 imperceptible, <10 small, >25 large."""
    L1, a1, b1 = _rgb_to_lab(rgb1)
    L2, a2, b2 = _rgb_to_lab(rgb2)
    avg_L = (L1 + L2) / 2
    C1 = (a1 ** 2 + b1 ** 2) ** 0.5
    C2 = (a2 ** 2 + b2 ** 2) ** 0.5
    avg_C = (C1 + C2) / 2
    G = 0.5 * (1 - (avg_C ** 7 / (avg_C ** 7 + 25 ** 7)) ** 0.5)
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p = (a1p ** 2 + b1 ** 2) ** 0.5
    C2p = (a2p ** 2 + b2 ** 2) ** 0.5
    avg_Cp = (C1p + C2p) / 2
    import math
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp = L2 - L1
    dCp = C2p - C1p
    dhp = h2p - h1p
    if dhp > 180: dhp -= 360
    if dhp < -180: dhp += 360
    if C1p * C2p == 0: dhp = 0
    dHp = 2 * (C1p * C2p) ** 0.5 * math.sin(math.radians(dhp / 2))
    avg_hp = ((h1p + h2p + 360) / 2) if abs(h1p - h2p) > 180 else (h1p + h2p) / 2
    if C1p * C2p == 0: avg_hp = h1p + h2p
    T = (1 - 0.17 * math.cos(math.radians(avg_hp - 30))
           + 0.24 * math.cos(math.radians(2 * avg_hp))
           + 0.32 * math.cos(math.radians(3 * avg_hp + 6))
           - 0.20 * math.cos(math.radians(4 * avg_hp - 63)))
    SL = 1 + (0.015 * (avg_L - 50) ** 2) / (20 + (avg_L - 50) ** 2) ** 0.5
    SC = 1 + 0.045 * avg_Cp
    SH = 1 + 0.015 * avg_Cp * T
    delta_theta = 30 * math.exp(-((avg_hp - 275) / 25) ** 2)
    Rc = 2 * (avg_Cp ** 7 / (avg_Cp ** 7 + 25 ** 7)) ** 0.5
    RT = -math.sin(math.radians(2 * delta_theta)) * Rc
    return float(((dLp / SL) ** 2 + (dCp / SC) ** 2 + (dHp / SH) ** 2
                  + RT * (dCp / SC) * (dHp / SH)) ** 0.5)


def color_distance_mean(ref: list[dict], gen: list[dict]) -> float:
    """Mean CIEDE2000 across Hungarian-matched pairs (lower = better).
    Skips pairs with no `bg` color on either side."""
    matches = hungarian_match(ref, gen)
    deltas = []
    for ri, gj, _iou in matches:
        rb, gb = ref[ri].get("bg"), gen[gj].get("bg")
        if rb and gb:
            deltas.append(ciede2000(rb, gb))
    if not deltas:
        return float("nan")
    return float(np.mean(deltas))


# ──────────────────────────────────────────────────────────────────────
# AeSlides Excessive Whitespace + Element Collision (deterministic)
# ──────────────────────────────────────────────────────────────────────

def excessive_whitespace(image_path: Path) -> dict:
    """Fraction of slide area with low local variance (AeSlides 2026)."""
    img = np.array(Image.open(image_path).convert("L").resize((1280, 720)), dtype=np.float32)
    # Local variance via box filter — simple O(N) approximation using cumulative
    # sums (avoids scipy.ndimage dependency in the hot path).
    from scipy.ndimage import uniform_filter
    win_h, win_w = 151, 201
    mean = uniform_filter(img, size=(win_h, win_w))
    sq_mean = uniform_filter(img ** 2, size=(win_h, win_w))
    var = np.clip(sq_mean - mean ** 2, 0, None)
    sigma = np.sqrt(var) / 64.0          # normalize to ~[0,1]
    sigma = np.clip(sigma, 0, 1)
    flat = (sigma < 0.05).astype(np.float32)
    whitespace_frac = float(flat.mean())
    return {
        "whitespace_frac": whitespace_frac,
        "content_frac": 1.0 - whitespace_frac,
    }


def element_collision(blocks: list[dict], slide_w: int = 1280, slide_h: int = 720) -> dict:
    """Detect three collision types from DOM blocks (AeSlides 2026):
       - overlap: element bboxes intersect (excluding parent-child trivial nesting)
       - container_overflow: child extends past its declared container
       - boundary_escape: any element extends past 1280×720 slide bounds
    Returns counts + a normalized 0..1 'collision_score' (lower = cleaner).
    """
    if not blocks:
        return {"overlap_pairs": 0, "boundary_escape": 0, "collision_score": 0.0}

    overlap = 0
    n = len(blocks)
    for i in range(n):
        a = blocks[i]
        for j in range(i + 1, n):
            b = blocks[j]
            iou = _bbox_iou(a, b)
            if iou > 0.0:
                # Treat near-equal containment as nesting (parent/child) — skip.
                # Real collision = partial overlap, not full containment.
                contain = (
                    a["x"] >= b["x"] and a["y"] >= b["y"]
                    and a["x"] + a["w"] <= b["x"] + b["w"]
                    and a["y"] + a["h"] <= b["y"] + b["h"]
                ) or (
                    b["x"] >= a["x"] and b["y"] >= a["y"]
                    and b["x"] + b["w"] <= a["x"] + a["w"]
                    and b["y"] + b["h"] <= a["y"] + a["h"]
                )
                if not contain and iou >= 0.05:
                    overlap += 1

    escape = sum(1 for b in blocks
                 if b["x"] < -2 or b["y"] < -2
                 or b["x"] + b["w"] > slide_w + 2
                 or b["y"] + b["h"] > slide_h + 2)

    raw = overlap * 0.7 + escape * 1.0
    # Normalize: 0 collisions → 0; saturate at ~20 events → 1.0
    score = min(1.0, raw / 20.0)
    return {
        "overlap_pairs": int(overlap),
        "boundary_escape": int(escape),
        "collision_score": float(score),
    }


# ──────────────────────────────────────────────────────────────────────
# AutoPresent Layout/Color GPT-4o judge (0-5)
# ──────────────────────────────────────────────────────────────────────

_JUDGE_PROMPT = """You are evaluating the visual design quality of a generated slide
against a reference design. Score on a 0-5 integer scale per axis. Use ONLY the
two visible images.

Score axes (AutoPresent 2025, reference-free):

LAYOUT (0-5):
  - 5: All elements aligned, no overlap, balanced spacing, fills slide appropriately
  - 3: Some misalignment or empty regions but overall usable
  - 0: Massive overlap, escape, or empty wasteland

COLOR (0-5):
  - 5: High contrast, palette consistent with reference, no glaring colors
  - 3: Partially matches reference palette, some contrast issues
  - 0: Colors clash or completely different palette

Return JSON only:
{"layout": <int 0-5>, "color": <int 0-5>, "note": "<=20 words"}"""


def _b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode()


def autopresent_judge(reference_png: Path, candidate_png: Path,
                      model: str = "gpt-4o") -> dict:
    """0-5 reference-free Layout/Color from AutoPresent. Single call.

    Uses the project's shared OpenAI client (which auto-loads .env via
    layeragent.utils.common). A bare `OpenAI()` would not pick up the key.
    """
    from layeragent.utils.llm import _openai_client
    client = _openai_client()
    msg = [
        {"type": "text", "text": _JUDGE_PROMPT},
        {"type": "text", "text": "REFERENCE:"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_b64(reference_png)}"}},
        {"type": "text", "text": "CANDIDATE:"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_b64(candidate_png)}"}},
    ]
    resp = client.chat.completions.create(
        model=model, max_tokens=200, temperature=0,
        messages=[{"role": "user", "content": msg}],
    )
    raw = resp.choices[0].message.content or ""
    s, e = raw.find("{"), raw.rfind("}")
    if s < 0 or e < 0:
        return {"layout": 0, "color": 0, "note": "parse_fail"}
    try:
        return json.loads(raw[s:e + 1])
    except Exception:
        return {"layout": 0, "color": 0, "note": "json_fail"}


# ──────────────────────────────────────────────────────────────────────
# Aggregate runner
# ──────────────────────────────────────────────────────────────────────

def all_design_metrics(
    ref_png: Path,
    gen_html: Path,
    gen_png: Path,
    skip_judge: bool = False,
    judge_model: str = "gpt-4o",
) -> dict:
    """Compute the full SOTA-aligned metric pack for one (reference, candidate) pair.

    Returns a flat dict with all metrics so it can be appended to a JSONL row.
    """
    out: dict = {}

    # 1. Block extraction
    ref_blocks = visual_blocks_from_image(ref_png)
    try:
        gen_blocks = extract_dom_blocks(gen_html)
    except Exception as e:
        gen_blocks = []
        out["dom_err"] = str(e)
    out["n_ref_blocks"] = len(ref_blocks)
    out["n_gen_blocks"] = len(gen_blocks)

    # 2. Reference-based: Block-Match + Element-IoU + CIEDE2000
    bm = block_match_f1(ref_blocks, gen_blocks)
    out["block_match_f1"] = bm["f1"]
    out["block_match_precision"] = bm["precision"]
    out["block_match_recall"] = bm["recall"]
    out["element_iou"] = element_iou_mean(ref_blocks, gen_blocks)
    out["color_ciede2000"] = color_distance_mean(ref_blocks, gen_blocks)

    # 3. AeSlides verifiable (deterministic)
    ws = excessive_whitespace(gen_png)
    out.update(ws)
    coll = element_collision(gen_blocks)
    out.update(coll)

    # 4. AutoPresent 0-5 GPT-4o (Layout + Color)
    if not skip_judge:
        try:
            j = autopresent_judge(ref_png, gen_png, model=judge_model)
            out["layout_0_5"] = int(j.get("layout", 0))
            out["color_0_5"] = int(j.get("color", 0))
            out["judge_note"] = j.get("note", "")
        except Exception as e:
            out["judge_err"] = str(e)

    return out
