"""Cross-VLM probing experiment — does the perception-generation gap hold
across multiple frontier models (GPT-4o, Claude, Gemini)?

For each (slide, VLM) pair:
  Stage A — VLM describes layers from the image (cached perception)
  Stage B — VLM generates HTML from the same image (baseline single prompt)
  Compute Layer Recall = how much of perceived structure survived in HTML

If gap = (1 - recall_B) is large across all 3 VLMs, the thesis
generalizes beyond GPT-4o (a single-model artifact would be invalidating).

Output:
  results/cross_vlm/probing.jsonl
  results/cross_vlm/summary.csv

Cost (50 slides × 3 VLMs × 2 stages = 300 calls):
  GPT-4o:  $5
  Claude:  $7  (Bedrock pricing varies)
  Gemini:  $3
  Total:   ~$15
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from experiments.probing.layer_tree import (
    PERCEPTION_PROMPT,
    layer_recall,
    lted as _lted,
    parse_html_tree,
    parse_perception_response,
)
from layeragent.utils.common import b64_image, load_active_specs


PERCEPTION_DIR = _ROOT / "data" / "eval_dataset" / "perception"
PERCEPTION_DIR.mkdir(parents=True, exist_ok=True)
GEN_DIR = _ROOT / "results" / "raw" / "cross_vlm"
GEN_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR = _ROOT / "results" / "cross_vlm"
OUT_DIR.mkdir(parents=True, exist_ok=True)


_BASELINE_GEN_PROMPT = """Convert this slide design into a single self-contained
HTML+CSS file. Use position:absolute layouts where needed. Reproduce all visual
elements you can identify: backgrounds, cards, icons, text, charts, tables.
Output ONLY the HTML code, no explanation, no markdown fences.
"""


# ─────────────────────────────────────────────────────────────────
# Per-VLM call adapters
# ─────────────────────────────────────────────────────────────────
def call_gpt4o(image_b64: str, prompt: str, max_tokens: int = 4000) -> str:
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return resp.choices[0].message.content or ""


def call_claude(image_b64: str, prompt: str, max_tokens: int = 4000) -> str:
    """Bedrock Claude Sonnet 4.5."""
    import boto3
    client = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    }
    resp = client.invoke_model(
        modelId=os.environ["BEDROCK_CLAUDE_SONNET_MODEL_ID"],
        body=json.dumps(body),
    )
    payload = json.loads(resp["body"].read())
    return payload["content"][0]["text"]


def call_gemini(image_b64: str, prompt: str, max_tokens: int = 4000) -> str:
    """Gemini 2.5 Flash."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GOOGLE_AI_STUDIO_KEY"])
    image_bytes = base64.b64decode(image_b64)
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            prompt,
        ],
        config=types.GenerateContentConfig(max_output_tokens=max_tokens),
    )
    return resp.text or ""


VLMS = {
    "gpt4o": call_gpt4o,
    "claude": call_claude,
    "gemini": call_gemini,
}


# ─────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────
def perception_path(vlm: str, slide_id: str) -> Path:
    return PERCEPTION_DIR / f"{vlm}_{slide_id}.txt"


def generation_path(vlm: str, slide_id: str) -> Path:
    out = GEN_DIR / vlm
    out.mkdir(exist_ok=True)
    return out / f"{slide_id}.html"


def run_pair(vlm: str, slide_id: str) -> dict | None:
    call_fn = VLMS[vlm]
    image_b64 = b64_image(slide_id)

    # Stage A
    p_path = perception_path(vlm, slide_id)
    if not p_path.exists():
        try:
            text = call_fn(image_b64, PERCEPTION_PROMPT, max_tokens=2000)
            p_path.write_text(text)
        except Exception as e:
            print(f"    ✗ perception failed: {e}")
            return None
    perception_text = p_path.read_text()
    tree_a = parse_perception_response(perception_text)

    # Stage B1 (baseline generation)
    g_path = generation_path(vlm, slide_id)
    if not g_path.exists():
        try:
            html = call_fn(image_b64, _BASELINE_GEN_PROMPT, max_tokens=8000)
            g_path.write_text(html)
        except Exception as e:
            print(f"    ✗ generation failed: {e}")
            return None
    gen_html = g_path.read_text()
    tree_b1 = parse_html_tree(gen_html)

    # Metrics
    recall = layer_recall(tree_a, tree_b1)
    return {
        "vlm": vlm,
        "slide_id": slide_id,
        "n_layers_perception": len(tree_a),
        "n_layers_generation": len(tree_b1),
        "layer_recall": recall,
        "gap": 1.0 - recall,
        "lted": _lted(tree_a, tree_b1),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--vlms", nargs="+", default=list(VLMS.keys()))
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    specs = load_active_specs()
    designs = [s["id"] for s in specs]
    if args.limit:
        designs = designs[:args.limit]

    print(f"[cross_vlm] vlms={args.vlms} slides={len(designs)}")
    rows: list[dict] = []
    t0 = time.time()
    for i, did in enumerate(designs, 1):
        for vlm in args.vlms:
            print(f"[{i:>3}/{len(designs)}] {vlm:>7} / {did} ...", flush=True)
            row = run_pair(vlm, did)
            if row:
                rows.append(row)
                print(f"    ✓ recall={row['layer_recall']:.2f}, gap={row['gap']:.2f}, "
                      f"perc_n={row['n_layers_perception']}, gen_n={row['n_layers_generation']}")
            time.sleep(0.5)

    # Save
    out_jsonl = OUT_DIR / "probing.jsonl"
    with out_jsonl.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n[cross_vlm] saved {len(rows)} rows → {out_jsonl}")

    # Summary
    print("\nMean by VLM:")
    print(f"{'VLM':<10} {'recall':>8} {'gap':>8} {'lted':>8} {'n':>5}")
    for vlm in args.vlms:
        sub = [r for r in rows if r["vlm"] == vlm]
        if not sub:
            continue
        m_rec = sum(r["layer_recall"] for r in sub) / len(sub)
        m_gap = sum(r["gap"] for r in sub) / len(sub)
        m_lted = sum(r["lted"] for r in sub) / len(sub)
        print(f"{vlm:<10} {m_rec:>8.2f} {m_gap:>8.2f} {m_lted:>8.2f} {len(sub):>5}")
    print(f"\nelapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
