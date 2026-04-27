"""Single-method MLLM judge — PPTEVAL style adapted for paper.

For each (slide, method) cell, the judge is shown:
  - Reference image (Gemini-generated original)
  - Generated PNG (rendered from method's HTML output)
  - Generated HTML text (structure / class names visible to judge)

Judge scores 4 criteria 1–7 with brief justification each:
  1. Visual Fidelity to Reference  — does the render look like the reference?
  2. Layer Structure Faithfulness  — is the layered hierarchy preserved?
  3. Content Completeness          — are all content elements present?
  4. Design Quality                — is the slide professional / clean?

Model: Azure-hosted GPT-5.4 (env: APIM_AOAI_ENDPOINT / APIM_AOAI_API_KEY / GPT_MODEL).
Pairwise comparison NOT used (per paper plan — single-method scoring).

Output:
  results/mllm_judge/scores.jsonl  (one row per method×slide cell)
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


METHODS = ["single_pass", "visual_cot", "cot_h_rag", "layeragent"]
RESULTS_DIR = _ROOT / "results"
SHOTS_DIR = RESULTS_DIR / "screenshots"
RAW_DIR = RESULTS_DIR / "raw"
JUDGE_DIR = RESULTS_DIR / "mllm_judge"
JUDGE_DIR.mkdir(parents=True, exist_ok=True)


_CRITERIA_PROMPT = """You are an expert design-to-code reviewer.

You are shown:
  1. REFERENCE IMAGE — the original slide design the system was asked to reproduce
  2. GENERATED IMAGE — a screenshot of the system's output rendered in a browser
  3. GENERATED HTML  — the source code of the system's output (truncated)

Score the system on 4 criteria, 1–7 (1=very poor, 4=acceptable, 7=excellent),
with one short justification (≤25 words) each:

A. **visual_fidelity** — does the rendered output look like the reference image?
   Consider colors, layout proportions, decorative elements, overall composition.

B. **layer_structure** — does the code preserve the layered hierarchy of the
   reference (background → cards → content → icons stacking, z-index discipline,
   nested grouping)? Consider DOM nesting depth, position:absolute usage,
   z-index discipline, semantic class organization.

C. **content_completeness** — are all the content elements visible in the
   rendered output (title, body items, data values, labels, icons)?
   Consider text presence, readability, no overlapping that hides information.

D. **design_quality** — independent of fidelity to reference, is the output
   itself a professional-looking slide (typography hierarchy, color harmony,
   spacing, alignment, no visual artifacts)?

Output STRICT JSON (no preamble, no markdown fences):
{{
  "visual_fidelity":      {{"score": <1-7>, "why": "<short>"}},
  "layer_structure":      {{"score": <1-7>, "why": "<short>"}},
  "content_completeness": {{"score": <1-7>, "why": "<short>"}},
  "design_quality":       {{"score": <1-7>, "why": "<short>"}}
}}

GENERATED HTML (first 3000 chars):
```html
{html_excerpt}
```
"""


def _b64(path: Path) -> str:
    with path.open("rb") as f:
        return base64.b64encode(f.read()).decode()


def _judge_one(client, model: str, ref_path: Path, gen_png: Path, gen_html: str) -> dict:
    html_excerpt = gen_html[:3000] if gen_html else ""
    prompt_text = _CRITERIA_PROMPT.format(html_excerpt=html_excerpt)
    resp = client.chat.completions.create(
        model=model,
        max_completion_tokens=2500,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{_b64(ref_path)}"}},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{_b64(gen_png)}"}},
                {"type": "text", "text": prompt_text},
            ],
        }],
    )
    raw = resp.choices[0].message.content or ""
    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        # Sometimes models add trailing commentary — try to extract first JSON object
        import re
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {"_parse_error": True, "_raw": raw[:500]}


def _build_client():
    """Build Azure OpenAI client for GPT-5.4 (per baselines/multi_model.py)."""
    from openai import AzureOpenAI
    endpoint = os.getenv("APIM_AOAI_ENDPOINT")
    key = os.getenv("APIM_AOAI_API_KEY")
    api_version = os.getenv("GPT_API_VERSION", "2025-04-01-preview")
    if not (endpoint and key):
        raise RuntimeError("Missing APIM_AOAI_ENDPOINT / APIM_AOAI_API_KEY in .env")
    return AzureOpenAI(azure_endpoint=endpoint, api_key=key, api_version=api_version)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--methods", nargs="+", default=METHODS)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--sleep", type=float, default=0.5)
    p.add_argument("--output", default=str(JUDGE_DIR / "scores.jsonl"))
    args = p.parse_args()

    from layeragent.utils.common import get_image_path, load_active_specs
    specs = load_active_specs()
    designs = [s["id"] for s in specs]
    if args.limit:
        designs = designs[:args.limit]

    model = os.getenv("GPT_MODEL", "gpt-5.4")
    client = _build_client()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Resume — skip already-judged cells
    existing: set[tuple[str, str]] = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                existing.add((row.get("method"), row.get("design_id")))
            except Exception:
                pass

    total = len(designs) * len(args.methods)
    print(f"[judge] model={model} cells={total} (already done: {len(existing)})")

    t0 = time.time()
    n_done = 0
    n_err = 0
    with out_path.open("a") as f:
        for did in designs:
            ref_path = get_image_path(did)
            for method in args.methods:
                key = (method, did)
                if key in existing:
                    continue
                gen_png = SHOTS_DIR / method / f"{did}.png"
                gen_html_path = RAW_DIR / method / f"{did}_seed0.html"
                row = {"method": method, "design_id": did}
                if not (ref_path.exists() and gen_png.exists()):
                    row["_error"] = f"missing files: ref={ref_path.exists()} gen_png={gen_png.exists()}"
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                    n_err += 1
                    continue
                gen_html = gen_html_path.read_text() if gen_html_path.exists() else ""
                try:
                    scores = _judge_one(client, model, ref_path, gen_png, gen_html)
                    row.update(scores)
                except Exception as e:
                    row["_error"] = f"{type(e).__name__}: {e}"
                    n_err += 1
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                n_done += 1
                vf = (scores.get("visual_fidelity") or {}).get("score") if "_error" not in row else "—"
                ls = (scores.get("layer_structure") or {}).get("score") if "_error" not in row else "—"
                cc = (scores.get("content_completeness") or {}).get("score") if "_error" not in row else "—"
                dq = (scores.get("design_quality") or {}).get("score") if "_error" not in row else "—"
                print(f"[{n_done:>3}] {method:>14} / {did:<32}  "
                      f"VF={vf} LS={ls} CC={cc} DQ={dq}", flush=True)
                if args.sleep > 0:
                    time.sleep(args.sleep)

    print(f"\n[judge] done in {time.time()-t0:.1f}s — {n_done} new, {n_err} errors")
    print(f"[judge] → {out_path}")


if __name__ == "__main__":
    main()
