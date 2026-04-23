#!/usr/bin/env python3
"""Gemini로 다양한 복잡도의 PPT 디자인 이미지 10개 생성."""

import asyncio
import base64
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent / "ai_apis" / "ppt"))

from core.services.nano_banana import generate_slide_image

OUTPUT_DIR = Path(__file__).parent / "data" / "experiment_designs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DESIGNS = [
    {
        "id": "design_01_timeline",
        "prompt": """Design a professional dark-themed presentation slide (1280x720px) showing a horizontal timeline with 4 milestone nodes.
Each node is a glowing circle connected by a gradient line. Below each node is a glassmorphism card with rounded corners.
Background: deep navy gradient with subtle grid pattern and radial glow spots.
Style: cyberpunk-inspired, neon cyan and purple accents, frosted glass cards with blur effect.
No text - only visual structure with placeholder areas for text.""",
    },
    {
        "id": "design_02_dashboard",
        "prompt": """Design a dark-themed data dashboard slide (1280x720px) with:
- Top section: large title area with accent line below
- Middle: 3 metric cards in a row, each with an icon circle at top, large number area, and small label
- Bottom: a wide chart area card spanning full width
Background: dark gradient with subtle dot pattern. Cards: glassmorphism with border glow.
Style: modern SaaS dashboard, blue and teal accent colors.
No text - only visual structure.""",
    },
    {
        "id": "design_03_comparison_split",
        "prompt": """Design a split-screen comparison slide (1280x720px) divided vertically in the middle.
Left half: dark blue background with 4 stacked items, each with an icon badge and text area
Right half: dark purple background with 4 stacked items, matching layout
Center divider: a glowing vertical line with a VS badge circle
Top: title area spanning full width
Style: competitive analysis look, neon accents, glassmorphism badges.
No text - only visual structure.""",
    },
    {
        "id": "design_04_pyramid",
        "prompt": """Design a pyramid/hierarchy slide (1280x720px) showing 3 tiers:
- Top tier: small card with crown/star icon (strategic level)
- Middle tier: 2 medium cards side by side (tactical level)
- Bottom tier: 3 wider cards in a row (operational level)
Background: dark gradient with geometric mesh pattern and ambient glow.
Cards: frosted glass with colored top borders (gold/silver/bronze progression).
Style: executive strategy presentation, dark theme with gold accents.
No text - only visual structure.""",
    },
    {
        "id": "design_05_hub_spoke",
        "prompt": """Design a hub-and-spoke diagram slide (1280x720px) with:
- Center: large circle with icon (hub)
- 6 smaller circles arranged around it, connected by gradient lines
- Each spoke circle sits inside a small glassmorphism card
Background: deep dark blue with radial glow from center, circuit board pattern.
Style: technology/network architecture, cyan and green accents, neon glow effects.
No text - only visual structure.""",
    },
    {
        "id": "design_06_before_after",
        "prompt": """Design a before/after transformation slide (1280x720px):
- Left section labeled area: 'before' state with 3 problem cards (red/orange tinted)
- Center: large arrow or transformation icon with glow effect
- Right section labeled area: 'after' state with 3 solution cards (green/blue tinted)
Background: gradient transitioning from warm dark (left) to cool dark (right).
Cards: glassmorphism with colored borders matching their section.
No text - only visual structure.""",
    },
    {
        "id": "design_07_feature_grid",
        "prompt": """Design a 2x3 feature grid slide (1280x720px) with:
- Title area at top
- 6 cards arranged in 2 rows of 3
- Each card has: icon badge (circle) at top-left, title area, description area, and small tag/badge at bottom
Background: dark navy with subtle diagonal lines and corner glow accents.
Cards: dark glassmorphism with subtle gradient borders and inner shadow.
Style: product feature showcase, purple and pink accents.
No text - only visual structure.""",
    },
    {
        "id": "design_08_roadmap",
        "prompt": """Design a horizontal roadmap slide (1280x720px) with:
- A horizontal gradient bar/track running across the middle
- 5 phase markers along the track, alternating above and below
- Each marker connects to a card with icon and content area
- Phase indicators: numbered circles on the track
Background: dark theme with subtle topographic map pattern, blue ambient glow.
Cards: frosted glass with phase-colored top accent bars.
No text - only visual structure.""",
    },
    {
        "id": "design_09_layered_stack",
        "prompt": """Design a layered architecture stack slide (1280x720px) with:
- 4 horizontal layers stacked vertically, each slightly overlapping the one below
- Top layer: smallest, brightest color (UI layer)
- Second layer: medium, slightly transparent (API layer)
- Third layer: wider, darker (Service layer)
- Bottom layer: widest, darkest (Infrastructure layer)
- Right side: vertical connector lines linking all layers
Background: deep black with subtle grid. Each layer: glassmorphism with different tint.
Style: software architecture diagram, rainbow gradient from top to bottom.
No text - only visual structure.""",
    },
    {
        "id": "design_10_stats_hero",
        "prompt": """Design a stats/impact hero slide (1280x720px) with:
- Left side: large hero number area with subtitle, taking 40% width
- Right side: 4 smaller stat cards stacked vertically, each with icon + number + label
- Background: dramatic dark gradient with large subtle circle shapes and light beam effect
- Decorative: floating geometric shapes (triangles, circles) with low opacity
Cards: glassmorphism with gradient bottom borders.
Style: annual report / investor deck, navy and gold accents.
No text - only visual structure.""",
    },
]


async def main():
    print(f"Generating {len(DESIGNS)} design images...")
    print(f"Output: {OUTPUT_DIR}")
    print()

    for i, design in enumerate(DESIGNS):
        design_id = design["id"]
        prompt = design["prompt"]
        output_path = OUTPUT_DIR / f"{design_id}.png"

        if output_path.exists():
            print(f"  [{i+1}/10] {design_id} — already exists, skip")
            continue

        print(f"  [{i+1}/10] {design_id}...", end=" ", flush=True)

        try:
            image_b64 = await generate_slide_image(
                prompt=prompt,
                aspect_ratio="16:9",
                image_size="1K",
            )

            if image_b64:
                img_bytes = base64.b64decode(image_b64)
                output_path.write_bytes(img_bytes)
                print(f"OK ({len(img_bytes)//1024}KB)")
            else:
                print("FAILED (no image)")
        except Exception as e:
            print(f"ERROR: {e}")

    print(f"\nDone! Files in {OUTPUT_DIR}")
    for f in sorted(OUTPUT_DIR.glob("*.png")):
        print(f"  {f.name} ({f.stat().st_size//1024}KB)")


if __name__ == "__main__":
    asyncio.run(main())
