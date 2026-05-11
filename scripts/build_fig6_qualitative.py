"""Build fig6_qualitative.png — 4-row × 3-col composite (reference / single_pass / LayerAgent).

Slides: design_03_comparison_split, design_05_hub_spoke, design_06_before_after, design_09_layered_stack.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

_ROOT = Path(__file__).resolve().parents[1]
REF = _ROOT / "data" / "eval_dataset" / "slides"
SP = _ROOT / "results" / "screenshots" / "single_pass"
LA = _ROOT / "results" / "screenshots" / "layeragent_v4"
OUT = _ROOT / "results" / "figures" / "fig6_qualitative.png"

SLIDES = [
    ("mekko_mckinsey_blue_finance",         "mekko"),
    ("line_chart_bcg_green_competition",    "line_chart (multi-series)"),
    ("matrix_2x2_mckinsey_blue_risk",       "matrix_2x2"),
    ("harvey_table_mckinsey_blue_options",  "harvey_table_advanced"),
]

CELL_W = 540
CELL_H = int(CELL_W * 9 / 16)  # 1280:720 → cell ratio
GUTTER = 12
PAD_TOP = 36     # column-header band
PAD_LEFT = 140   # row-label band
LABEL_FONT_SIZE = 18
HEADER_FONT_SIZE = 20


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]:
        p = Path(candidate)
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def main() -> None:
    font_h = _font(HEADER_FONT_SIZE)
    font_l = _font(LABEL_FONT_SIZE)

    n_rows, n_cols = len(SLIDES), 3
    W = PAD_LEFT + n_cols * (CELL_W + GUTTER) + GUTTER
    H = PAD_TOP + n_rows * (CELL_H + GUTTER) + GUTTER

    canvas = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(canvas)

    headers = ["Reference", "single_pass", "LayerAgent"]
    for j, h in enumerate(headers):
        x = PAD_LEFT + j * (CELL_W + GUTTER) + GUTTER
        bbox = draw.textbbox((0, 0), h, font=font_h)
        tw = bbox[2] - bbox[0]
        draw.text((x + (CELL_W - tw) // 2, 6), h, fill="black", font=font_h)

    for i, (sid, label) in enumerate(SLIDES):
        y_top = PAD_TOP + i * (CELL_H + GUTTER) + GUTTER
        # row label (wrap-friendly: place vertically centered)
        bbox = draw.textbbox((0, 0), label, font=font_l)
        draw.text((10, y_top + (CELL_H - (bbox[3] - bbox[1])) // 2 - 2),
                  label, fill="#333", font=font_l)
        for j, src_dir in enumerate([REF, SP, LA]):
            x = PAD_LEFT + j * (CELL_W + GUTTER) + GUTTER
            img_path = src_dir / f"{sid}.png"
            if not img_path.exists():
                draw.rectangle([x, y_top, x + CELL_W, y_top + CELL_H], outline="red", width=2)
                draw.text((x + 8, y_top + 8), f"missing: {img_path.name}", fill="red", font=font_l)
                continue
            with Image.open(img_path) as im:
                im_rgb = im.convert("RGB").resize((CELL_W, CELL_H), Image.LANCZOS)
            canvas.paste(im_rgb, (x, y_top))
            draw.rectangle([x, y_top, x + CELL_W - 1, y_top + CELL_H - 1],
                           outline="#D1D5DB", width=1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT, "PNG", optimize=True)
    print(f"→ {OUT} ({W}×{H})")


if __name__ == "__main__":
    main()
