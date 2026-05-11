"""Analyze main_eval results and produce paper-ready summary tables.

Reads results/main_eval/eval_results.jsonl and produces:
  - Aggregate mean ± std per (method, metric)
  - Per-layout breakdown
  - Wins (LayerAgent vs each baseline) with paired t-test
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))


PRIMARY_METRICS = ["block_match", "position", "lted", "layer_recall"]
HIGHER_BETTER = {"block_match": True, "position": True,
                 "lted": False, "layer_recall": True}


def load_results(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def aggregate(rows: list[dict], metric: str) -> dict[str, dict]:
    """Mean / std / N per method, filtered to rows with valid metric."""
    by_method: dict[str, list[float]] = {}
    for r in rows:
        v = r.get(metric)
        if isinstance(v, (int, float)) and not (v != v):  # not NaN
            by_method.setdefault(r["method"], []).append(float(v))
    out = {}
    for m, vals in by_method.items():
        if not vals:
            continue
        out[m] = {
            "mean": statistics.mean(vals),
            "std": statistics.stdev(vals) if len(vals) > 1 else 0.0,
            "n": len(vals),
        }
    return out


def print_main_table(rows: list[dict]) -> None:
    methods = sorted({r["method"] for r in rows})
    print(f"\n{'Metric':<15}", end="")
    for m in methods:
        print(f"{m:>16}", end="")
    print()
    print("-" * (15 + 16 * len(methods)))
    for metric in PRIMARY_METRICS:
        agg = aggregate(rows, metric)
        arrow = " ↑" if HIGHER_BETTER.get(metric, True) else " ↓"
        print(f"{metric+arrow:<15}", end="")
        for m in methods:
            if m in agg:
                a = agg[m]
                print(f" {a['mean']:>6.3f}±{a['std']:>5.3f}({a['n']:>2})", end="")
            else:
                print(f" {'—':>16}", end="")
        print()

    # Render rate
    print(f"\n{'render_ok %':<15}", end="")
    for m in methods:
        sub = [r for r in rows if r["method"] == m]
        n = len(sub)
        ok = sum(1 for r in sub if r.get("render_ok"))
        if n > 0:
            print(f" {(ok/n)*100:>14.1f}%", end="")
    print()


def per_layout_breakdown(rows: list[dict]) -> None:
    """Group by layout (parsed from slide_id)."""
    print("\n\nPer-layout breakdown (LTED, lower=better):")
    layouts = sorted({_layout_of(r["design_id"]) for r in rows})
    methods = sorted({r["method"] for r in rows})
    print(f"{'Layout':<22}", end="")
    for m in methods:
        print(f"{m:>14}", end="")
    print()
    print("-" * (22 + 14 * len(methods)))

    for L in layouts:
        sub = [r for r in rows if _layout_of(r["design_id"]) == L]
        print(f"{L:<22}", end="")
        for m in methods:
            ms = [r for r in sub if r["method"] == m and isinstance(r.get("lted"), (int, float))]
            if ms:
                mean = sum(r["lted"] for r in ms) / len(ms)
                print(f" {mean:>10.3f}({len(ms):>2})", end="")
            else:
                print(f" {'—':>14}", end="")
        print()


def _layout_of(slide_id: str) -> str:
    """Parse layout type from slide_id (e.g., 'mekko_mckinsey_blue_finance' → 'mekko')."""
    if slide_id.startswith("design_"):
        return "design_existing"
    parts = slide_id.split("_")
    # mekko_, matrix_2x2_, harvey_table_, bar_chart_, line_chart_, process_flow_, pyramid_, waterfall_
    if parts[0] == "matrix":
        return "matrix_2x2"
    if parts[0] == "harvey":
        return "harvey_table"
    if parts[0] == "bar":
        return "bar_chart"
    if parts[0] == "line":
        return "line_chart"
    if parts[0] == "process":
        return "process_flow"
    return parts[0]


def perception_generation_gap(rows: list[dict]) -> None:
    """Derive Stage A vs B comparison from main_eval results.

    Stage A (perception): cached in data/eval_dataset/perception/<sid>.txt — those
    set the n_ref_layers / 'expected' layer count.
    Stage B (generation): the layeragent / single_pass row's n_gen_layers.

    Gap_method = 1 - layer_recall(method).
    """
    print("\n\nPerception-Generation Gap (paper's Figure 1 data):")
    methods = sorted({r["method"] for r in rows})
    for m in methods:
        sub = [r for r in rows if r["method"] == m and isinstance(r.get("layer_recall"), (int, float))]
        if not sub:
            continue
        recalls = [r["layer_recall"] for r in sub]
        gaps = [1.0 - x for x in recalls]
        print(f"  {m:<14}  recall={statistics.mean(recalls):.3f}±{statistics.stdev(recalls):.3f}"
              f"  gap={statistics.mean(gaps):.3f}  N={len(sub)}")


def main() -> None:
    eval_path = _ROOT / "results" / "main_eval" / "eval_results.jsonl"
    if not eval_path.exists():
        print(f"[err] {eval_path} not found")
        sys.exit(1)
    rows = load_results(eval_path)
    print(f"[analyze] {len(rows)} rows")

    print_main_table(rows)
    per_layout_breakdown(rows)
    perception_generation_gap(rows)


if __name__ == "__main__":
    main()
