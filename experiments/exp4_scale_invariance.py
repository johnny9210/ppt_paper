"""exp4 — SOTA 일관성 (구 model-agnostic) 검증.

Conditions:
- A_baseline_gpt4o   (single-pass GPT-4o)
- A_baseline_gpt54   (single-pass GPT-5.4 via Azure)
- A_baseline_claude  (single-pass Claude 4.6 Opus via Bedrock)
- D_full_gpt4o       (LayerAgent on GPT-4o, reused from exp1)

Metrics: ConsistencyScore + CCR + CSS Richness + joint pass

Hypothesis H4:
    ConsistencyScore(GPT-5.4 single-pass) < ConsistencyScore(LayerAgent on GPT-4o)
    AND joint_pass(GPT-5.4 single-pass) < joint_pass(LayerAgent on GPT-4o)
=> 두 보장 실패가 SOTA closed VLM 전반에서 일관됨 (단계 분리가 핵심).
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
from baselines import multi_model as single_pass_multimodel
from experiments._adapter import layeragent_full
from experiments.metrics import consistency, ccr_cssrich
from experiments.exp2_content_isolation import collect_text_items, get_existing_html


CONDITIONS = [
    # (name, method, model_arg)
    ("A_gpt4o", single_pass_multimodel, "gpt-4o"),
    ("A_gpt54", single_pass_multimodel, "gpt-5.4"),
    ("A_claude_opus", single_pass_multimodel, "claude-4.6-opus"),
    ("D_full_gpt4o", layeragent_full, "gpt-4o"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_seeds", type=int, default=1)
    parser.add_argument("--out", type=str, default="results/raw/exp4_scale_invariance.jsonl")
    args = parser.parse_args()

    out_path = _ROOT / "final_test" / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    specs = _common.load_active_specs()
    meta = _common.load_meta()
    print(f"[exp4] {len(CONDITIONS)} conditions × {len(specs)} designs × {args.n_seeds} seeds")

    with out_path.open("w") as fout:
        for spec in specs:
            sid = spec["id"]
            design = _common.get_design_by_id(meta, sid)
            text_items = collect_text_items(design["content"])
            for cond_name, method, model in CONDITIONS:
                for seed in range(args.n_seeds):
                    t0 = time.time()
                    existing = get_existing_html(cond_name, sid, seed)
                    if existing:
                        body_match = existing.split('overflow:hidden;position:relative;">', 1)
                        html = body_match[1].rsplit("</div>\n</body>", 1)[0] if len(body_match) > 1 else existing
                        elapsed = 0.0
                        reused = True
                    else:
                        print(f"  [{cond_name}] {sid} seed={seed} model={model} ...", flush=True)
                        try:
                            html = method.run(sid, seed=seed, model=model)
                            _common.save_run(cond_name, sid, seed, html)
                            elapsed = time.time() - t0
                            reused = False
                        except Exception as e:
                            traceback.print_exc()
                            rec = {"exp": "exp4", "condition": cond_name, "model": model,
                                   "slide_id": sid, "seed": seed,
                                   "elapsed_s": round(time.time() - t0, 2),
                                   "ok": False, "error": f"{type(e).__name__}: {e}"}
                            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            fout.flush()
                            print(f"     ✗ FAIL: {e}")
                            continue

                    cs = consistency.consistency_score(html)
                    ccr_res = ccr_cssrich.ccr(text_items, html)
                    css_res = ccr_cssrich.css_richness(html)
                    joint = 1 if (ccr_res["ccr"] >= 0.7 and css_res["css_richness"] >= 10) else 0

                    rec = {
                        "exp": "exp4", "condition": cond_name, "model": model,
                        "slide_id": sid, "seed": seed,
                        "elapsed_s": round(elapsed, 2), "reused": reused,
                        "consistency_score": cs["score"], "n_card_classes": cs["n_card_classes"],
                        "ccr": ccr_res["ccr"], "css_richness": css_res["css_richness"],
                        "joint_pass": joint,
                        "ok": True,
                    }
                    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fout.flush()
                    tag = "♻" if reused else "✓"
                    print(f"  {tag} [{cond_name}] {sid}: cons={rec['consistency_score']:.2f} CCR={rec['ccr']:.2f} CSS={rec['css_richness']} joint={joint}")

    print(f"[exp4] done. results: {out_path}")


if __name__ == "__main__":
    main()
