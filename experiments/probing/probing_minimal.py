"""Minimal probing experiment — perception-generation gap on existing 10 designs.

Tests: does the same VLM (GPT-4o) describe layer structure correctly when ASKED
about it, but lose it when GENERATING HTML from the same image?

Stages:
  A  : VLM perception — image → "list layers" prompt → layer tree T_A
  B1 : Baseline generation — image → "convert to HTML" prompt → HTML → tree T_B1
  B2 : LayerAgent generation — image → run() → existing HTML → tree T_B2

Metrics (per slide):
  Recall_A   = layer_recall(T_A, T_A)              ≡ 1.0  (sanity)
  Recall_B1  = layer_recall(T_A, T_B1)             baseline coverage
  Recall_B2  = layer_recall(T_A, T_B2)             ours coverage

  Gap_baseline = Recall_A − Recall_B1
  Gap_ours     = Recall_A − Recall_B2
  Closure      = Gap_baseline − Gap_ours

Output: probing_results.jsonl + console summary table.
"""
from __future__ import annotations

import base64
import json
import statistics
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from openai import OpenAI

from experiments.probing.layer_tree import (
    PERCEPTION_PROMPT,
    layer_recall,
    lted,
    parse_html_tree,
    parse_perception_response,
    LayerNode,
)
from layeragent.utils.common import b64_image, load_meta


_DESIGNS = [
    "design_01_timeline", "design_02_dashboard", "design_03_comparison_split",
    "design_04_pyramid", "design_05_hub_spoke", "design_06_before_after",
    "design_07_feature_grid", "design_08_roadmap", "design_09_layered_stack",
    "design_10_stats_hero",
]

_BASELINE_GEN_PROMPT = """Convert this slide design into a single self-contained
HTML+CSS file. Use position:absolute layouts where needed. Reproduce all visual
elements you can identify: backgrounds, cards, icons, text, charts, tables.
Output ONLY the HTML code, no explanation, no markdown fences.
"""

_OUT_PATH = _ROOT / "experiments" / "probing" / "probing_results.jsonl"


def vision_call_gpt4o(client: OpenAI, image_b64: str, prompt: str, max_tokens: int = 2000) -> str:
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


def read_layeragent_html(slide_id: str) -> str | None:
    p = _ROOT / "results" / "raw" / "layeragent" / f"{slide_id}_seed0.html"
    if p.exists():
        return p.read_text()
    return None


def run_one(client: OpenAI, slide_id: str) -> dict:
    print(f"\n[probe] {slide_id}")
    image_b64 = b64_image(slide_id)

    # Stage A — Perception
    print("  Stage A (perception) ...", flush=True)
    perc_text = vision_call_gpt4o(client, image_b64, PERCEPTION_PROMPT)
    tree_a = parse_perception_response(perc_text)
    print(f"    → {len(tree_a)} layers detected")
    if not tree_a:
        print(f"    raw: {perc_text[:200]}")

    # Stage B1 — Baseline generation
    print("  Stage B1 (baseline gen) ...", flush=True)
    base_html = vision_call_gpt4o(client, image_b64, _BASELINE_GEN_PROMPT, max_tokens=8000)
    tree_b1 = parse_html_tree(base_html)
    print(f"    → {len(tree_b1)} layers detected")

    # Stage B2 — LayerAgent (cached output)
    layer_html = read_layeragent_html(slide_id)
    if layer_html:
        tree_b2 = parse_html_tree(layer_html)
        print(f"  Stage B2 (LayerAgent cached) → {len(tree_b2)} layers detected")
    else:
        tree_b2 = []
        print("  Stage B2: cached HTML missing — skipping")

    # Metrics
    rec_b1 = layer_recall(tree_a, tree_b1)
    rec_b2 = layer_recall(tree_a, tree_b2) if tree_b2 else None
    lted_b1 = lted(tree_a, tree_b1)
    lted_b2 = lted(tree_a, tree_b2) if tree_b2 else None
    gap_baseline = 1.0 - rec_b1
    gap_ours = (1.0 - rec_b2) if rec_b2 is not None else None
    closure = (gap_baseline - gap_ours) if gap_ours is not None else None

    return {
        "slide_id": slide_id,
        "n_layers_A": len(tree_a),
        "n_layers_B1": len(tree_b1),
        "n_layers_B2": len(tree_b2),
        "tree_A": [n.to_dict() for n in tree_a],
        "tree_B1": [n.to_dict() for n in tree_b1],
        "tree_B2": [n.to_dict() for n in tree_b2],
        "recall_B1": rec_b1,
        "recall_B2": rec_b2,
        "lted_B1": lted_b1,
        "lted_B2": lted_b2,
        "gap_baseline": gap_baseline,
        "gap_ours": gap_ours,
        "closure": closure,
        "_baseline_html_excerpt": base_html[:500],
        "_perception_excerpt": perc_text[:500],
    }


def summarize(results: list[dict]) -> None:
    print("\n" + "=" * 78)
    print("RESULTS — Per-slide breakdown")
    print("=" * 78)
    print(f"{'slide':<32} {'A_n':>4} {'B1_n':>5} {'B2_n':>5}  "
          f"{'rec_B1':>7} {'rec_B2':>7}  {'gap_base':>9} {'gap_ours':>9}  {'closure':>8}")
    print("-" * 78)
    for r in results:
        rb1 = f"{r['recall_B1']:.2f}" if r['recall_B1'] is not None else "—"
        rb2 = f"{r['recall_B2']:.2f}" if r['recall_B2'] is not None else "—"
        gb = f"{r['gap_baseline']:.2f}" if r['gap_baseline'] is not None else "—"
        go = f"{r['gap_ours']:.2f}" if r['gap_ours'] is not None else "—"
        cl = f"{r['closure']:.2f}" if r['closure'] is not None else "—"
        print(f"{r['slide_id']:<32} {r['n_layers_A']:>4} {r['n_layers_B1']:>5} "
              f"{r['n_layers_B2']:>5}  {rb1:>7} {rb2:>7}  {gb:>9} {go:>9}  {cl:>8}")

    valid = [r for r in results if r['recall_B2'] is not None]
    if valid:
        print("-" * 78)
        m_rec_b1 = statistics.mean(r['recall_B1'] for r in valid)
        m_rec_b2 = statistics.mean(r['recall_B2'] for r in valid)
        m_gap_b = statistics.mean(r['gap_baseline'] for r in valid)
        m_gap_o = statistics.mean(r['gap_ours'] for r in valid)
        m_clos = statistics.mean(r['closure'] for r in valid)
        print(f"{'MEAN':<32} {'':>4} {'':>5} {'':>5}  "
              f"{m_rec_b1:>7.2f} {m_rec_b2:>7.2f}  {m_gap_b:>9.2f} {m_gap_o:>9.2f}  {m_clos:>8.2f}")
        print("\nINTERPRETATION:")
        if m_gap_b > 0.30 and m_gap_o < m_gap_b * 0.5:
            print("  ✓ Strong gap in baseline + significant closure by LayerAgent.")
            print("  ✓ Paper thesis (perception-generation gap) supported.")
        elif m_gap_b > 0.15:
            print("  ~ Moderate baseline gap; closure measurable but not dramatic.")
        else:
            print("  ✗ Baseline gap small — paper thesis weakly supported on this set.")


def main() -> None:
    client = OpenAI()
    print(f"[probe] running on {len(_DESIGNS)} designs")
    print(f"[probe] output → {_OUT_PATH}\n")

    results: list[dict] = []
    with _OUT_PATH.open("w") as f:
        for sid in _DESIGNS:
            try:
                r = run_one(client, sid)
                results.append(r)
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
            except Exception as e:
                print(f"  ✗ error: {e}")

    summarize(results)


if __name__ == "__main__":
    main()
