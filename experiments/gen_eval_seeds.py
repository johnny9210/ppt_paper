"""Generate consulting-style slide seeds via Gemini 2.5 image generation.

Test run: 3 seed prompts to verify Gemini can produce the layout types we need
(Mekko chart, 2x2 matrix, comparison table) before scaling to 50.

Usage:
    python -m experiments.gen_eval_seeds
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")

OUT_DIR = _ROOT / "data" / "eval_dataset" / "seeds_test"
OUT_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.environ.get("GOOGLE_AI_STUDIO_KEY") or os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("Set GOOGLE_AI_STUDIO_KEY (or GEMINI_API_KEY) in .env")


# Three seed prompts — Mekko / 2x2 matrix / Comparison Table.
# Each follows McKinsey/BCG/Bain action-title conventions.
SEEDS = [
    {
        "id": "seed_01_mekko_mckinsey",
        "prompt": """Generate a single professional consulting slide image (1280×720, PNG).

Layout: McKinsey-style action title slide with a Marimekko (Mekko) chart.

Slide structure:
- Top: Action title in Georgia serif, ~28pt, dark navy color, 1-2 lines:
  "APAC retail drove 67% of FY2025 revenue growth, led by China and India"
- Optional subtitle below in lighter gray, smaller (~14pt):
  "Revenue contribution by region × product category"
- Body (center, ~75% of slide): Marimekko chart with:
  - X-axis: 4 regions (APAC 45%, NAM 28%, EMEA 18%, LATAM 9%)
  - Y-axis stacked within each: 3 product categories (Apparel, Electronics, Home)
  - Each block labeled with revenue $B figure (e.g., "$12.4B")
  - APAC blocks highlighted in McKinsey blue (#003B71), others in gray tones
- Bottom right: small footer "Source: Internal financial data, FY2025"
  + page number "5"
- Background: clean white
- Color palette: deep navy (#003B71), light blue accent, neutral grays
- Typography: Georgia for title, Arial for body labels
- Layout: clean, generous white space, no clutter
- One clear insight, no decorative elements""",
    },
    {
        "id": "seed_02_matrix_bcg",
        "prompt": """Generate a single professional consulting slide image (1280×720, PNG).

Layout: BCG-style 2×2 matrix slide (BCG Growth-Share Matrix variant).

Slide structure:
- Top: Action title in bold sans-serif, ~26pt, dark color, 1-2 lines:
  "Three product lines are in the 'Stars' quadrant, justifying 70% of capex"
- Body: Large 2×2 matrix occupying ~70% of slide:
  - X-axis (bottom): "Market Share" (Low → High)
  - Y-axis (left, rotated): "Market Growth Rate" (Low → High)
  - Four quadrants labeled: "Question Marks" (top-left), "Stars" (top-right),
    "Dogs" (bottom-left), "Cash Cows" (bottom-right)
  - 6-8 circles representing products, each sized by revenue, placed in quadrants:
    - 3 circles in "Stars" (top-right, in BCG green #00A651, larger)
    - 2 circles in "Cash Cows" (bottom-right, lighter green)
    - 2 circles in "Question Marks" (top-left, gray)
    - 1 circle in "Dogs" (bottom-left, light gray)
  - Each circle labeled with product name (e.g., "ProdA", "ProdB")
- Bottom right: footer "Source: Strategic review, Q4 2025" + page "12"
- Background: white
- Color palette: BCG green (#00A651) accent, gray tones, no decorative
- Typography: clean sans-serif (Helvetica/Arial), 2 weights only
- Layout: minimal, professional, single insight clear from title""",
    },
    {
        "id": "seed_03_table_bain",
        "prompt": """Generate a single professional consulting slide image (1280×720, PNG).

Layout: Bain-style comparison table slide with Harvey balls.

Slide structure:
- Top: Action title in dark serif, ~26pt, 1-2 lines:
  "Vendor B leads on 4 of 5 evaluation criteria, justifying selection"
- Body: Comparison table occupying ~70% of slide:
  - Header row: Empty corner cell, then "Vendor A", "Vendor B", "Vendor C"
  - 5 row labels in left column:
    "Total Cost of Ownership", "Implementation speed", "Feature completeness",
    "Vendor stability", "Customer references"
  - Cells contain Harvey balls (filled circles ranging from 0% to 100% fill):
    - Vendor A: medium fills (50%, 75%, 50%, 100%, 50%)
    - Vendor B: high fills (100%, 100%, 75%, 75%, 100%) — accent color Bain red (#CC0033)
    - Vendor C: low-medium (25%, 50%, 25%, 50%, 75%)
  - Cells beside Harvey balls have brief justification text (e.g., "$2.4M lower 5yr TCO")
  - Vendor B column subtly highlighted with thin red border
- Below table: "Recommendation: proceed with Vendor B for Q1 2026 procurement"
- Bottom right: footer "Source: Vendor RFP scoring, Dec 2025" + page "8"
- Background: white
- Color palette: Bain red (#CC0033) accent, dark gray text, neutral table
- Typography: serif title (Georgia), sans-serif body (Arial)
- Layout: clean table, generous row height for readability""",
    },
]


DEFAULT_MODEL = "gemini-3-pro-image-preview"  # latest, highest quality
FALLBACK_MODEL = "gemini-2.5-flash-image"


def generate_one(client: genai.Client, seed: dict, model: str = DEFAULT_MODEL) -> Path | None:
    """Generate one slide image. Returns saved path or None on failure."""
    print(f"[gen] {seed['id']} (model={model}) ...", flush=True)
    try:
        response = client.models.generate_content(
            model=model,
            contents=seed["prompt"],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
    except Exception as e:
        print(f"  ✗ API error: {e}")
        if model != FALLBACK_MODEL:
            print(f"  → retrying with {FALLBACK_MODEL}")
            return generate_one(client, seed, model=FALLBACK_MODEL)
        return None

    # Walk the response parts looking for inline_data with image
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            data = part.inline_data.data
            if isinstance(data, str):
                data = base64.b64decode(data)
            out_path = OUT_DIR / f"{seed['id']}.png"
            out_path.write_bytes(data)
            print(f"  ✓ saved → {out_path} ({len(data)} bytes)")
            return out_path

    # No image found
    text_parts = [p.text for p in response.candidates[0].content.parts if getattr(p, "text", None)]
    print(f"  ✗ no image in response. text response: {' '.join(text_parts)[:200]}")
    return None


def main() -> None:
    client = genai.Client(api_key=API_KEY)
    print(f"[gen] output dir: {OUT_DIR}")
    print(f"[gen] generating {len(SEEDS)} seeds\n")
    saved = []
    for seed in SEEDS:
        p = generate_one(client, seed)
        if p:
            saved.append(p)
    print(f"\n[gen] done. saved {len(saved)}/{len(SEEDS)} images.")
    if saved:
        print("[gen] open with:")
        for p in saved:
            print(f"  open {p}")


if __name__ == "__main__":
    main()
