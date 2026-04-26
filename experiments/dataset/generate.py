"""Batch-generate the 40 consulting-style seeds via Gemini 3 Pro Image Preview.

Output:
  data/eval_dataset/slides/{seed_id}.png       — generated images
  data/eval_dataset/meta.json                   — full dataset metadata

Strategy:
  - Sequential generation with rate-limit handling (~1 req/sec safe)
  - Skip already-generated (resumable)
  - Per-image error tolerance: failure logs but doesn't abort batch
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from experiments.dataset.seeds import SEEDS


_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

_OUT_DIR = _ROOT / "data" / "eval_dataset" / "slides"
_OUT_DIR.mkdir(parents=True, exist_ok=True)
_META_PATH = _ROOT / "data" / "eval_dataset" / "meta.json"

_API_KEY = os.environ.get("GOOGLE_AI_STUDIO_KEY") or os.environ.get("GEMINI_API_KEY")
if not _API_KEY:
    raise RuntimeError("Set GOOGLE_AI_STUDIO_KEY in .env")

_MODEL = "gemini-3-pro-image-preview"
_FALLBACK = "gemini-2.5-flash-image"


def generate_one(client, seed: dict, model: str = _MODEL) -> Path | None:
    out_path = _OUT_DIR / f"{seed['id']}.png"
    try:
        response = client.models.generate_content(
            model=model,
            contents=seed["prompt"],
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )
    except Exception as e:
        print(f"    ✗ API error: {e}")
        if model != _FALLBACK:
            print(f"    → retrying with {_FALLBACK}")
            return generate_one(client, seed, model=_FALLBACK)
        return None

    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            data = part.inline_data.data
            if isinstance(data, str):
                data = base64.b64decode(data)
            out_path.write_bytes(data)
            return out_path
    return None


def import_existing_designs() -> list[dict]:
    """Copy the 10 existing dark-glass design images into the eval dataset."""
    src = _ROOT / "data" / "experiment_designs"
    entries: list[dict] = []
    for png in sorted(src.glob("design_*.png")):
        sid = png.stem  # e.g. "design_01_timeline"
        dst = _OUT_DIR / f"{sid}.png"
        if not dst.exists():
            shutil.copy2(png, dst)
        entries.append({
            "id": sid,
            "layout": sid.split("_", 2)[2],   # crude — e.g. "timeline"
            "theme": "dark_glass",
            "domain": "general",
            "source": "existing_design_images (Gemini-generated, dark glassmorphism)",
        })
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0, help="seed index to start at")
    parser.add_argument("--limit", type=int, default=None, help="max seeds to generate")
    parser.add_argument("--sleep", type=float, default=1.0, help="seconds between calls")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="skip seeds whose PNG already exists (default on)")
    args = parser.parse_args()

    client = genai.Client(api_key=_API_KEY)

    # Snapshot existing 10 designs into the dataset folder
    existing = import_existing_designs()

    # Generate the 40 new seeds
    seeds = SEEDS
    if args.limit is not None:
        seeds = seeds[args.start:args.start + args.limit]
    else:
        seeds = seeds[args.start:]

    print(f"[gen] dataset dir: {_OUT_DIR}")
    print(f"[gen] new seeds to attempt: {len(seeds)}")
    print(f"[gen] existing designs imported: {len(existing)}\n")

    generated: list[dict] = []
    failed: list[str] = []
    t0 = time.time()
    for i, seed in enumerate(seeds, 1):
        out_path = _OUT_DIR / f"{seed['id']}.png"
        if args.skip_existing and out_path.exists():
            print(f"[{i:>2}/{len(seeds)}] {seed['id']} — skip (exists)")
            generated.append({**seed, "path": str(out_path), "_status": "cached"})
            continue
        print(f"[{i:>2}/{len(seeds)}] {seed['id']} ...", flush=True)
        result = generate_one(client, seed)
        if result:
            print(f"    ✓ {result.stat().st_size//1024} KB ({time.time()-t0:.1f}s elapsed)")
            generated.append({**seed, "path": str(result), "_status": "generated"})
        else:
            failed.append(seed["id"])
        if args.sleep > 0:
            time.sleep(args.sleep)

    # Write dataset metadata
    meta = {
        "version": "1.0",
        "total": len(generated) + len(existing),
        "n_new": len(generated),
        "n_existing": len(existing),
        "failed": failed,
        "model": _MODEL,
        "slides": existing + generated,
    }
    _META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"\n[gen] done. generated {len(generated)}/{len(seeds)} new, failed {len(failed)}")
    print(f"[gen] dataset meta → {_META_PATH}")
    if failed:
        print(f"[gen] failed seeds: {failed}")


if __name__ == "__main__":
    main()
