"""Analyze MLLM-judge results and merge with main_eval for full picture."""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))


CRITERIA = ["visual_fidelity", "layer_structure", "content_completeness", "design_quality"]


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def get_score(row: dict, criterion: str):
    v = row.get(criterion)
    if isinstance(v, dict):
        return v.get("score")
    return None


def aggregate_judge(rows: list[dict]) -> None:
    methods = sorted({r["method"] for r in rows if "_error" not in r})
    print("\n=== MLLM Judge — Aggregate (N=48 per method) ===\n")
    print(f"{'Criterion':<24}", end="")
    for m in methods:
        print(f"{m:>14}", end="")
    print()
    print("-" * (24 + 14 * len(methods)))
    for c in CRITERIA:
        print(f"{c:<24}", end="")
        for m in methods:
            scores = [get_score(r, c) for r in rows
                      if r["method"] == m and "_error" not in r]
            scores = [s for s in scores if isinstance(s, (int, float))]
            if scores:
                mean = statistics.mean(scores)
                std = statistics.stdev(scores) if len(scores) > 1 else 0
                print(f" {mean:>5.2f}±{std:.2f}({len(scores):>2})", end="")
            else:
                print(f"{'—':>14}", end="")
        print()


def per_layout(rows: list[dict]) -> None:
    print("\n=== Per-layout, layer_structure score (LayerAgent vs best baseline) ===\n")
    layouts: dict[str, list[dict]] = {}
    for r in rows:
        if "_error" in r:
            continue
        sid = r["design_id"]
        if sid.startswith("design_"):
            layout = "design_existing"
        else:
            parts = sid.split("_")
            if parts[0] == "matrix":
                layout = "matrix_2x2"
            elif parts[0] == "harvey":
                layout = "harvey_table"
            elif parts[0] == "bar":
                layout = "bar_chart"
            elif parts[0] == "line":
                layout = "line_chart"
            elif parts[0] == "process":
                layout = "process_flow"
            else:
                layout = parts[0]
        layouts.setdefault(layout, []).append(r)

    print(f"{'Layout':<22}", end="")
    for c in ["visual_fidelity", "layer_structure", "content_completeness", "design_quality"]:
        print(f"{c[:14]:>16}", end="")
    print()
    print("-" * (22 + 16 * 4))

    for layout, layout_rows in sorted(layouts.items()):
        print(f"{layout:<22}", end="")
        for c in CRITERIA:
            la_scores = [get_score(r, c) for r in layout_rows if r["method"] == "layeragent"]
            la_scores = [s for s in la_scores if isinstance(s, (int, float))]
            base_scores = []
            for m in ("single_pass", "visual_cot", "cot_h_rag"):
                base_scores.extend(get_score(r, c) for r in layout_rows if r["method"] == m)
            base_scores = [s for s in base_scores if isinstance(s, (int, float))]
            if la_scores and base_scores:
                la_m = statistics.mean(la_scores)
                base_m = statistics.mean(base_scores)
                delta = la_m - base_m
                marker = "★" if delta > 0.5 else (" " if delta > -0.5 else "✗")
                print(f" {marker}{la_m:>4.1f} vs {base_m:>4.1f}", end="")
            else:
                print(f"{'—':>16}", end="")
        print()


def merge_with_main_eval(judge_rows: list[dict]) -> None:
    main = _ROOT / "results" / "main_eval" / "eval_results.jsonl"
    if not main.exists():
        print("\n[merge] main_eval not found")
        return
    main_rows = load_jsonl(main)
    main_idx = {(r["method"], r["design_id"]): r for r in main_rows}

    print("\n=== Combined: MLLM-judge × deterministic metrics ===\n")
    methods = sorted({r["method"] for r in judge_rows if "_error" not in r})
    print(f"{'method':<14}{'LS judge':>10}{'VF judge':>10}{'CC judge':>10}{'DQ judge':>10}{'LTED↓':>10}{'Recall↑':>10}{'SSIM↑':>10}")
    print("-" * 84)
    for m in methods:
        jr = [r for r in judge_rows if r["method"] == m and "_error" not in r]
        ls_scores = [get_score(r, "layer_structure") for r in jr]
        vf_scores = [get_score(r, "visual_fidelity") for r in jr]
        cc_scores = [get_score(r, "content_completeness") for r in jr]
        dq_scores = [get_score(r, "design_quality") for r in jr]
        ls_scores = [s for s in ls_scores if isinstance(s, (int, float))]
        vf_scores = [s for s in vf_scores if isinstance(s, (int, float))]
        cc_scores = [s for s in cc_scores if isinstance(s, (int, float))]
        dq_scores = [s for s in dq_scores if isinstance(s, (int, float))]

        lted_vals = [r.get("lted") for r in main_rows if r["method"] == m]
        lted_vals = [v for v in lted_vals if isinstance(v, (int, float))]
        recall_vals = [r.get("layer_recall") for r in main_rows if r["method"] == m]
        recall_vals = [v for v in recall_vals if isinstance(v, (int, float))]
        ssim_vals = [r.get("ssim") for r in main_rows if r["method"] == m]
        ssim_vals = [v for v in ssim_vals if isinstance(v, (int, float))]

        def avg(xs):
            return statistics.mean(xs) if xs else float("nan")
        print(f"{m:<14}"
              f"{avg(ls_scores):>10.2f}{avg(vf_scores):>10.2f}{avg(cc_scores):>10.2f}{avg(dq_scores):>10.2f}"
              f"{avg(lted_vals):>10.3f}{avg(recall_vals):>10.3f}{avg(ssim_vals):>10.3f}")


def main() -> None:
    judge_path = _ROOT / "results" / "mllm_judge" / "scores.jsonl"
    if not judge_path.exists():
        print(f"[err] {judge_path} not found")
        sys.exit(1)
    rows = load_jsonl(judge_path)
    valid = [r for r in rows if "_error" not in r]
    err = [r for r in rows if "_error" in r]
    print(f"[analyze] {len(rows)} rows ({len(valid)} valid, {len(err)} errors)")

    aggregate_judge(rows)
    per_layout(rows)
    merge_with_main_eval(rows)


if __name__ == "__main__":
    main()
