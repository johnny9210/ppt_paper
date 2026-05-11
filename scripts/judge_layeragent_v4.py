"""MLLM judge — LayerAgent v4 outputs only, vs reference.

Runs the 4-criteria GPT-5.4 judge on 50 layeragent_v4 outputs to produce
per-layout absolute scores (no method comparison). Output is consumed
by fig3 regeneration.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from experiments.metrics.single_method_judge import _CRITERIA_PROMPT, _parse_json, _build_client

REF_DIR = _ROOT / "data" / "eval_dataset" / "slides"
GEN_PNG_DIR = _ROOT / "results" / "screenshots" / "layeragent_v4"
GEN_HTML_DIR = _ROOT / "results" / "raw" / "layeragent_v4"
OUT = _ROOT / "results" / "mllm_judge" / "scores_layeragent_v4.jsonl"
OUT.parent.mkdir(parents=True, exist_ok=True)


def b64(path: Path) -> str:
    with path.open("rb") as f:
        return base64.b64encode(f.read()).decode()


def judge_one(client, model: str, ref: Path, gen: Path, html: str) -> dict:
    prompt = _CRITERIA_PROMPT.format(html_excerpt=(html or "")[:3000])
    resp = client.chat.completions.create(
        model=model, max_completion_tokens=2500,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64(ref)}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64(gen)}"}},
            {"type": "text", "text": prompt},
        ]}],
    )
    return _parse_json(resp.choices[0].message.content or "")


def main() -> None:
    slides = sorted(p.stem for p in REF_DIR.glob("*.png"))
    existing = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            if line.strip():
                try:
                    existing.add(json.loads(line)["design_id"])
                except Exception:
                    pass
    print(f"[judge_v4] {len(slides)} slides total, {len(existing)} already done")

    model = os.getenv("GPT_MODEL", "gpt-5.4")
    client = _build_client()
    t0 = time.time()
    n_done = 0
    with OUT.open("a") as f:
        for sid in slides:
            if sid in existing:
                continue
            ref = REF_DIR / f"{sid}.png"
            gen = GEN_PNG_DIR / f"{sid}.png"
            htmlp = GEN_HTML_DIR / f"{sid}_seed0.html"
            row = {"method": "layeragent", "design_id": sid}
            if not (ref.exists() and gen.exists()):
                row["_error"] = f"missing ref={ref.exists()} gen={gen.exists()}"
                f.write(json.dumps(row, ensure_ascii=False) + "\n"); f.flush()
                continue
            html = htmlp.read_text() if htmlp.exists() else ""
            try:
                scores = judge_one(client, model, ref, gen, html)
                row.update(scores)
            except Exception as e:
                row["_error"] = f"{type(e).__name__}: {e}"
            f.write(json.dumps(row, ensure_ascii=False) + "\n"); f.flush()
            n_done += 1
            vf = (scores.get("visual_fidelity") or {}).get("score") if "_error" not in row else "—"
            ls = (scores.get("layer_structure") or {}).get("score") if "_error" not in row else "—"
            cc = (scores.get("content_completeness") or {}).get("score") if "_error" not in row else "—"
            dq = (scores.get("design_quality") or {}).get("score") if "_error" not in row else "—"
            print(f"[{n_done:>2}] {sid:<55}  VF={vf} LS={ls} CC={cc} DQ={dq}", flush=True)
            time.sleep(0.3)

    print(f"\n[judge_v4] done in {time.time()-t0:.1f}s — {n_done} new")
    print(f"[judge_v4] → {OUT}")


if __name__ == "__main__":
    main()
