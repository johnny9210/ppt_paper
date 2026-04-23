"""exp2 — RQ2 Content-Style Isolation.

Conditions: A, B (Visual CoT), C (CoT+H-RAG), D₂ (LayerAgent − Text Inserter), D
Generations: 5 conditions × 5 designs × 1+ seeds.

Reuses A, D outputs from exp1/raw if present (skip re-generation).

Metrics: CCR (Content Completeness Rate), CSS Richness, joint pass rate
Hypothesis H2: joint_pass(D) − joint_pass(D₂) ≥ 0.25
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

from final_test.methods import _common
from final_test.methods import (
    single_pass, visual_cot, cot_h_rag,
    layeragent_no_textinserter, layeragent_full,
)
from final_test.metrics import consistency, ccr_cssrich

CONDITIONS = {
    "A_baseline": single_pass,
    "B_visual_cot": visual_cot,
    "C_cot_hrag": cot_h_rag,
    "D2_no_textinserter": layeragent_no_textinserter,
    "D_full": layeragent_full,
}


def collect_text_items(content: dict) -> list[str]:
    """flatten 모든 텍스트 콘텐츠 (CCR 계산용)."""
    items: list[str] = []
    for k, v in content.items():
        if k in ("speaker_script", "infographic_script"):
            continue
        if isinstance(v, str) and v.strip():
            items.append(v.strip())
        elif isinstance(v, list):
            for it in v:
                if isinstance(it, dict):
                    for vv in it.values():
                        if isinstance(vv, str) and vv.strip():
                            items.append(vv.strip())
                elif isinstance(it, str):
                    items.append(it.strip())
        elif isinstance(v, dict):
            items.extend(collect_text_items(v))
    return items


def get_existing_html(condition: str, sid: str, seed: int) -> str | None:
    p = _ROOT / "final_test" / "results" / "raw" / condition / f"{sid}_seed{seed}.html"
    return p.read_text() if p.exists() else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_seeds", type=int, default=1)
    parser.add_argument("--out", type=str, default="results/raw/exp2_content_isolation.jsonl")
    parser.add_argument("--reuse_existing", action="store_true", default=True,
                        help="reuse outputs in results/raw/{condition}/ if present (default: yes)")
    args = parser.parse_args()

    out_path = _ROOT / "final_test" / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    specs = _common.load_active_specs()
    meta = _common.load_meta()

    print(f"[exp2] {len(CONDITIONS)} conditions × {len(specs)} designs × {args.n_seeds} seeds")
    print(f"[exp2] writing to: {out_path}")

    with out_path.open("w") as fout:
        for spec in specs:
            sid = spec["id"]
            design = _common.get_design_by_id(meta, sid)
            text_items = collect_text_items(design["content"])
            for cond_name, method in CONDITIONS.items():
                for seed in range(args.n_seeds):
                    t0 = time.time()
                    existing = get_existing_html(cond_name, sid, seed) if args.reuse_existing else None
                    if existing:
                        # 기존 HTML이 있으면 재사용 (exp1에서 생성된 A, D, D₁ 출력 등)
                        # 단, exp2는 D2가 필요한데 D₁(no_stylenorm)은 다른 condition임
                        # 정확히 condition 이름 일치해야만 재사용
                        body_match = existing.split('overflow:hidden;position:relative;">', 1)
                        html = body_match[1].rsplit("</div>\n</body>", 1)[0] if len(body_match) > 1 else existing
                        elapsed = 0.0
                        reused = True
                    else:
                        print(f"  [{cond_name}] {sid} seed={seed} ...", flush=True)
                        try:
                            html = method.run(sid, seed=seed, model="gpt-4o")
                            _common.save_run(cond_name, sid, seed, html)
                            elapsed = time.time() - t0
                            reused = False
                        except Exception as e:
                            traceback.print_exc()
                            rec = {"exp": "exp2", "condition": cond_name, "slide_id": sid, "seed": seed,
                                   "elapsed_s": round(time.time() - t0, 2), "ok": False,
                                   "error": f"{type(e).__name__}: {e}"}
                            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            fout.flush()
                            print(f"     ✗ FAIL")
                            continue

                    ccr_res = ccr_cssrich.ccr(text_items, html)
                    css_res = ccr_cssrich.css_richness(html)
                    joint_pass = 1 if (ccr_res["ccr"] >= 0.7 and css_res["css_richness"] >= 10) else 0
                    cs = consistency.consistency_score(html)

                    rec = {
                        "exp": "exp2", "condition": cond_name, "slide_id": sid, "seed": seed,
                        "elapsed_s": round(elapsed, 2), "reused": reused,
                        "html_len": len(html),
                        "ccr": ccr_res["ccr"], "ccr_n_found": ccr_res["n_found"], "ccr_n_items": ccr_res["n_items"],
                        "css_richness": css_res["css_richness"],
                        "joint_pass": joint_pass,
                        "consistency_score": cs["score"], "n_card_classes": cs["n_card_classes"],
                        "ok": True,
                    }
                    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fout.flush()
                    tag = "♻" if reused else "✓"
                    print(f"  {tag} [{cond_name}] {sid}: CCR={rec['ccr']:.2f} CSS={rec['css_richness']} joint={joint_pass} cons={rec['consistency_score']:.2f}")

    print(f"[exp2] done. results: {out_path}")


if __name__ == "__main__":
    main()
