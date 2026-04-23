"""exp1 — RQ1 Cross-Element Consistency.

Conditions: A (single-pass), D₁ (LayerAgent − Style Normalizer), D (LayerAgent full)
Generations: 3 conditions × 5 designs × 1+ seeds.

For each generation:
- Run method, save HTML to results/raw/{method}/{slide_id}_seed{N}.html
- Compute ConsistencyScore on the resulting HTML
- Append run record to results/raw/exp1_consistency.jsonl

After all generations: aggregate per-condition stats + paired Wilcoxon (D vs D₁).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from layeragent.utils import common as _common
from baselines import single_pass
from experiments._adapter import layeragent_full, layeragent_no_stylenorm
from experiments.metrics import consistency

CONDITIONS = {
    "A_baseline": single_pass,
    "D1_no_stylenorm": layeragent_no_stylenorm,
    "D_full": layeragent_full,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_seeds", type=int, default=1)
    parser.add_argument("--out", type=str, default="results/raw/exp1_consistency.jsonl")
    parser.add_argument("--only", type=str, default=None, help="comma list of slide_ids to limit")
    args = parser.parse_args()

    out_path = _ROOT / "final_test" / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    specs = _common.load_active_specs()
    if args.only:
        keep = set(args.only.split(","))
        specs = [s for s in specs if s["id"] in keep]

    print(f"[exp1] {len(CONDITIONS)} conditions × {len(specs)} designs × {args.n_seeds} seeds")
    print(f"[exp1] writing to: {out_path}")

    with out_path.open("w") as fout:
        for spec in specs:
            sid = spec["id"]
            for cond_name, method in CONDITIONS.items():
                for seed in range(args.n_seeds):
                    t0 = time.time()
                    print(f"  [{cond_name}] {sid} seed={seed} ...", flush=True)
                    try:
                        html = method.run(sid, seed=seed, model="gpt-4o")
                        score = consistency.consistency_score(html)
                        _common.save_run(cond_name, sid, seed, html)
                        rec = {
                            "exp": "exp1",
                            "condition": cond_name,
                            "slide_id": sid,
                            "seed": seed,
                            "elapsed_s": round(time.time() - t0, 2),
                            "html_len": len(html),
                            "consistency_score": score["score"],
                            "n_cards": score["n_cards"],
                            "per_property_cv": score["per_property_cv"],
                            "ok": True,
                        }
                    except Exception as e:
                        traceback.print_exc()
                        rec = {
                            "exp": "exp1",
                            "condition": cond_name,
                            "slide_id": sid,
                            "seed": seed,
                            "elapsed_s": round(time.time() - t0, 2),
                            "ok": False,
                            "error": f"{type(e).__name__}: {e}",
                        }
                    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fout.flush()
                    if rec.get("ok"):
                        print(f"     ✓ {rec['elapsed_s']}s, score={rec['consistency_score']:.3f}, n_cards={rec['n_cards']}")
                    else:
                        print(f"     ✗ FAIL: {rec.get('error', '')[:100]}")

    print(f"[exp1] done. results: {out_path}")


if __name__ == "__main__":
    main()
