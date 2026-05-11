"""5-way VLM ranking on McKinsey reference.

Why this exists: pixel/perceptual metrics (CLIP/LPIPS) rank single_pass > v3
because they reward brightness-distribution match (single_pass is "mostly
white-blank" like the reference's whitespace-dominant gestalt) over actual
content fidelity. To sanity-check the upgrade we ask a VLM to rank the 5
candidates directly.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from layeragent.utils.llm import _openai_client  # noqa: E402

PNG_DIR = ROOT / "results" / "mckinsey_eval" / "png"
REFERENCE = ROOT / "data" / "eval_dataset" / "slides" / "process_flow_mckinsey_blue_transformation.png"

CANDIDATES = [
    "layeragent_v3",
    "layeragent_v1",
    "single_pass",
    "visual_cot",
    "cot_h_rag",
]

PROMPT = """You are a professional design fidelity evaluator.

You will see a REFERENCE slide image, then 5 CANDIDATE renderings labeled C1..C5.
Each candidate is a generated HTML+CSS rendering attempting to reproduce the
REFERENCE design.

Score each candidate (1-10, integer) against the REFERENCE on these axes:
- Layout (5 cards arranged correctly with proper spacing/shape?)
- Color (same palette: white background, dark navy headers, gray footer?)
- Structure (header band + body + footer separation visible?)
- Content (3 bullets per card + quarter date footer?)
- Overall (gestalt fidelity)

Return STRICT JSON ONLY:
{
  "C1": {"layout": int, "color": int, "structure": int, "content": int, "overall": int, "note": "<=20 words"},
  "C2": {...},
  "C3": {...},
  "C4": {...},
  "C5": {...},
  "ranking": ["C?", "C?", "C?", "C?", "C?"]   // best→worst by overall
}"""


def _b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode()


def _img_msg(label: str, p: Path) -> list:
    return [
        {"type": "text", "text": label},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_b64(p)}"}},
    ]


def main():
    client = _openai_client()
    content = [{"type": "text", "text": PROMPT}, *_img_msg("REFERENCE:", REFERENCE)]
    label_map = {}
    for i, name in enumerate(CANDIDATES, start=1):
        cid = f"C{i}"
        label_map[cid] = name
        p = PNG_DIR / f"{name}.png"
        content += _img_msg(f"{cid}:", p)

    print(f"[vlm_rank] candidates: {label_map}")

    resp = client.chat.completions.create(
        model="gpt-4o", max_tokens=2000, temperature=0,
        messages=[{"role": "user", "content": content}],
    )
    raw = resp.choices[0].message.content
    print("\n--- VLM raw ---")
    print(raw)

    # parse
    s = raw.find("{")
    e = raw.rfind("}")
    if s == -1 or e == -1:
        print("parse failed")
        return
    parsed = json.loads(raw[s:e + 1])

    # remap labels
    print("\n=== Per-candidate scores (label → method) ===")
    rows = []
    for cid, scores in parsed.items():
        if cid == "ranking":
            continue
        name = label_map.get(cid, cid)
        rows.append((name, scores))

    print(f"{'method':<20} layout color struct content OVERALL  note")
    print("-" * 110)
    for name, s in sorted(rows, key=lambda x: -x[1].get("overall", 0)):
        print(f"{name:<20} {s.get('layout',0):>6} {s.get('color',0):>5} {s.get('structure',0):>6} {s.get('content',0):>7} {s.get('overall',0):>8}  {s.get('note','')[:55]}")

    print("\n=== Ranking (best → worst) ===")
    for cid in parsed.get("ranking", []):
        print(f"  {cid} = {label_map.get(cid, cid)}")

    out = ROOT / "results" / "mckinsey_eval" / "vlm_ranking.json"
    out.write_text(json.dumps({"label_map": label_map, "result": parsed}, indent=2, ensure_ascii=False))
    print(f"\nsaved → {out}")


if __name__ == "__main__":
    main()
