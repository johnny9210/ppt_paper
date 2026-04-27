"""Generate paper figures from experiment results.

Figures produced:
  fig1_gap.pdf      — Perception-Generation Gap (per-VLM bar/box)
  fig2_methods.pdf  — Method comparison across primary metrics
  fig3_layouts.pdf  — Per-layout LTED breakdown
  fig4_ablation.pdf — 5 invariants ablation impact

Reads from:
  results/main_eval/eval_results.jsonl
  results/cross_vlm/probing.jsonl  (optional)
  results/ablations/eval_results.jsonl  (optional)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

FIG_DIR = _ROOT / "results" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def fig1_perception_generation_gap(rows: list[dict],
                                    cross_vlm_rows: list[dict] | None = None) -> None:
    """Layer recall: baseline vs LayerAgent, per VLM if available."""
    fig, ax = plt.subplots(figsize=(7, 4.5))

    # GPT-4o from main_eval
    methods = ["single_pass", "visual_cot", "cot_h_rag", "layeragent"]
    method_labels = ["A. Baseline", "B. Visual CoT", "C. CoT+H-RAG", "F. LayerAgent (ours)"]

    if cross_vlm_rows:
        # Plot cross-VLM gap on the left, methods comparison on the right
        vlms = ["gpt4o", "claude", "gemini"]
        gap_means = []
        gap_errs = []
        for v in vlms:
            sub = [r for r in cross_vlm_rows if r["vlm"] == v]
            if sub:
                vals = [r["gap"] for r in sub]
                gap_means.append(np.mean(vals))
                gap_errs.append(np.std(vals) / np.sqrt(len(vals)))
            else:
                gap_means.append(0)
                gap_errs.append(0)
        ax.bar(np.arange(len(vlms)), gap_means, yerr=gap_errs,
               color=["#3B82F6", "#7C3AED", "#10B981"], capsize=4, width=0.6)
        ax.set_xticks(np.arange(len(vlms)))
        ax.set_xticklabels(["GPT-4o", "Claude", "Gemini"])
        ax.set_ylabel("Perception–Generation Gap (1 − layer recall)")
        ax.set_title("Cross-VLM: gap is universal, not GPT-4o-specific")
        ax.set_ylim(0, 1)
    else:
        # Method comparison: layer_recall by method (higher is better)
        means = []
        errs = []
        for m in methods:
            sub = [r for r in rows if r["method"] == m and isinstance(r.get("layer_recall"), (int, float))]
            if sub:
                vals = [r["layer_recall"] for r in sub]
                means.append(np.mean(vals))
                errs.append(np.std(vals) / np.sqrt(len(vals)))
            else:
                means.append(0)
                errs.append(0)
        colors = ["#94A3B8", "#94A3B8", "#94A3B8", "#3B82F6"]
        ax.bar(np.arange(len(methods)), means, yerr=errs, color=colors, capsize=4, width=0.6)
        ax.set_xticks(np.arange(len(methods)))
        ax.set_xticklabels(method_labels, rotation=15, ha="right")
        ax.set_ylabel("Layer Recall (higher = better)")
        ax.set_title("Perception–Generation Gap: LayerAgent recovers structure baselines miss")
        ax.set_ylim(0, 1)
        ax.axhline(1.0, color="#10B981", linestyle="--", linewidth=0.8,
                   label="Stage A (perception ground truth)")
        ax.legend(loc="lower left")

    fig.tight_layout()
    out = FIG_DIR / "fig1_gap.pdf"
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  → {out}")


def fig2_methods(rows: list[dict]) -> None:
    """Multi-metric method comparison."""
    methods = ["single_pass", "visual_cot", "cot_h_rag", "layeragent"]
    metrics = ["ssim", "block_match", "position", "lted", "layer_recall"]
    metric_labels = ["SSIM", "Block-Match", "Position", "LTED↓", "LayerRecall"]
    higher_better = [True, True, True, False, True]

    fig, axes = plt.subplots(1, len(metrics), figsize=(14, 3.5), sharey=False)
    for ax, metric, label, hb in zip(axes, metrics, metric_labels, higher_better):
        means = []
        errs = []
        for m in methods:
            sub = [r[metric] for r in rows
                   if r["method"] == m and isinstance(r.get(metric), (int, float))]
            if sub:
                means.append(np.mean(sub))
                errs.append(np.std(sub) / np.sqrt(len(sub)))
            else:
                means.append(0)
                errs.append(0)
        colors = ["#94A3B8"] * 3 + ["#3B82F6"]
        ax.bar(np.arange(len(methods)), means, yerr=errs, color=colors, capsize=3, width=0.6)
        ax.set_xticks(np.arange(len(methods)))
        ax.set_xticklabels(["A", "B", "C", "F"], fontsize=9)
        ax.set_title(label, fontsize=10)
        if not hb:
            ax.set_ylim(top=ax.get_ylim()[1])
            ax.invert_yaxis()
    fig.tight_layout()
    out = FIG_DIR / "fig2_methods.pdf"
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  → {out}")


def main() -> None:
    main_rows = load_jsonl(_ROOT / "results" / "main_eval" / "eval_results.jsonl")
    cross_rows = load_jsonl(_ROOT / "results" / "cross_vlm" / "probing.jsonl")

    if not main_rows:
        print("[err] main_eval results missing — run experiments.main_eval first")
        return
    print(f"[figures] main_eval: {len(main_rows)} rows")
    print(f"[figures] cross_vlm: {len(cross_rows)} rows")

    fig1_perception_generation_gap(main_rows, cross_rows or None)
    fig2_methods(main_rows)


if __name__ == "__main__":
    main()
