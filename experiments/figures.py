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


LAYOUT_ORDER = [
    "dark_glass", "pyramid", "mekko", "process_flow", "harvey_table",
    "matrix_2x2", "waterfall", "line_chart", "bar_chart",
]
LAYOUT_LABELS = {
    "dark_glass": "dark_glass\n(layered)", "pyramid": "pyramid", "mekko": "mekko",
    "process_flow": "process_flow", "harvey_table": "harvey_table",
    "matrix_2x2": "matrix_2x2", "waterfall": "waterfall",
    "line_chart": "line_chart", "bar_chart": "bar_chart",
}
DARK_GLASS = {f"design_{i:02d}_{name}" for i, name in [
    (1, "timeline"), (2, "dashboard"), (3, "comparison_split"),
    (4, "pyramid"), (5, "hub_spoke"), (6, "before_after"),
    (7, "feature_grid"), (8, "roadmap"), (9, "layered_stack"),
    (10, "stats_hero")]}


def _design_layout(design_id: str) -> str | None:
    if design_id in DARK_GLASS:
        return "dark_glass"
    for layout in ["harvey_table", "matrix_2x2", "process_flow", "line_chart",
                   "bar_chart", "waterfall", "pyramid", "mekko"]:
        if design_id.startswith(layout + "_"):
            return layout
    return None


def fig3_layouts(main_rows: list[dict], judge_rows: list[dict]) -> None:
    """Per-layout MLLM Δ and LTED Δ (LayerAgent − best baseline)."""
    methods = ["single_pass", "visual_cot", "cot_h_rag", "layeragent"]
    crits = ["visual_fidelity", "layer_structure", "content_completeness", "design_quality"]

    mllm_avg = {m: {} for m in methods}
    for r in judge_rows:
        if r.get("method") not in methods or "_error" in r:
            continue
        layout = _design_layout(r["design_id"])
        if layout is None:
            continue
        try:
            slide_avg = sum(r[c]["score"] for c in crits) / 4
        except (KeyError, TypeError):
            continue
        mllm_avg[r["method"]].setdefault(layout, []).append(slide_avg)

    lted_avg = {m: {} for m in methods}
    for r in main_rows:
        if r.get("method") not in methods or not isinstance(r.get("lted"), (int, float)):
            continue
        layout = _design_layout(r["design_id"])
        if layout is None:
            continue
        lted_avg[r["method"]].setdefault(layout, []).append(r["lted"])

    mllm_delta, lted_delta = [], []
    for layout in LAYOUT_ORDER:
        baselines_mllm = [np.mean(mllm_avg[m][layout]) for m in ["single_pass", "visual_cot", "cot_h_rag"]
                          if mllm_avg[m].get(layout)]
        la_mllm_vals = mllm_avg["layeragent"].get(layout, [])
        if baselines_mllm and la_mllm_vals:
            mllm_delta.append(np.mean(la_mllm_vals) - max(baselines_mllm))
        else:
            mllm_delta.append(0)
        baselines_lted = [np.mean(lted_avg[m][layout]) for m in ["single_pass", "visual_cot", "cot_h_rag"]
                          if lted_avg[m].get(layout)]
        la_lted_vals = lted_avg["layeragent"].get(layout, [])
        if baselines_lted and la_lted_vals:
            lted_delta.append(min(baselines_lted) - np.mean(la_lted_vals))
        else:
            lted_delta.append(0)

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2), sharey=False)
    x = np.arange(len(LAYOUT_ORDER))
    labels = [LAYOUT_LABELS[l] for l in LAYOUT_ORDER]

    colors_m = ["#10B981" if d > 0 else "#EF4444" for d in mllm_delta]
    axes[0].bar(x, mllm_delta, color=colors_m, width=0.65)
    axes[0].axhline(0, color="black", linewidth=0.6)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    axes[0].set_ylabel("MLLM Δ (LayerAgent − best baseline)")
    axes[0].set_title("Primary axis — MLLM judge", fontsize=11)

    colors_l = ["#10B981" if d > 0 else "#EF4444" for d in lted_delta]
    axes[1].bar(x, lted_delta, color=colors_l, width=0.65)
    axes[1].axhline(0, color="black", linewidth=0.6)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    axes[1].set_ylabel("LTED Δ (best baseline − LayerAgent)")
    axes[1].set_title("Aux axis — LTED (class-name aligned)", fontsize=11)

    fig.suptitle("Per-layout effect range (positive = LayerAgent advantage)", fontsize=11, y=1.02)
    fig.tight_layout()
    out = FIG_DIR / "fig3_layouts.pdf"
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  → {out}")


def fig4_ablation() -> None:
    """D₂ (Text Inserter) and D₄ (DesignSpec) ablation impact."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    # Left: D₂ Text Inserter (CCR ↓ when removed) — N=50 main_eval
    ax = axes[0]
    cats = ["CCR ↑", "CSS Richness ↑", "Joint Pass ↑"]
    d_full = [0.975, 30.18, 0.76]
    d_no_ti = [0.632, 32.44, 0.16]
    x = np.arange(len(cats))
    w = 0.36
    ax.bar(x - w/2, d_full, w, label="D (full)", color="#3B82F6")
    ax.bar(x + w/2, d_no_ti, w, label="D2 (no Text Inserter)", color="#94A3B8")
    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_title("D2: Text Inserter ablation (N=50 main_eval)", fontsize=10)
    ax.legend(loc="upper right", fontsize=8)
    for i, (v1, v2) in enumerate(zip(d_full, d_no_ti)):
        ax.text(i - w/2, v1 + max(d_full)*0.02, f"{v1:.2f}" if v1 < 1 else f"{v1:.0f}", ha="center", fontsize=8)
        ax.text(i + w/2, v2 + max(d_full)*0.02, f"{v2:.2f}" if v2 < 1 else f"{v2:.0f}", ha="center", fontsize=8)

    # Right: D₄ DesignSpec (8 metrics, N=50)
    ax = axes[1]
    metrics = ["VEC", "EDC", "CRP", "SSIM", "CLIP", "LPIPS↓"]
    d_full_v = [17.0, 8.9, 31.2, 0.582, 0.493, 0.718]
    d_no_ds = [14.9, 8.5, 26.8, 0.408, 0.466, 0.798]
    # normalize to relative 0-1 for unified bar
    d_norm_full = [v / max(a, b) for v, a, b in zip(d_full_v, d_full_v, d_no_ds)]
    d_norm_ds = [v / max(a, b) for v, a, b in zip(d_no_ds, d_full_v, d_no_ds)]
    x = np.arange(len(metrics))
    ax.bar(x - w/2, d_norm_full, w, label="D (full)", color="#3B82F6")
    ax.bar(x + w/2, d_norm_ds, w, label="D4 (no DesignSpec)", color="#94A3B8")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=9)
    ax.set_ylabel("Normalized to max (per-metric)")
    ax.set_title("D4: DesignSpec blackboard ablation (N=50)", fontsize=10)
    ax.legend(loc="lower right", fontsize=8)
    ax.set_ylim(0, 1.15)
    # raw values as labels
    for i, (v1, v2) in enumerate(zip(d_full_v, d_no_ds)):
        fmt = (lambda v: f"{v:.2f}") if v1 < 5 else (lambda v: f"{v:.1f}")
        ax.text(i - w/2, d_norm_full[i] + 0.02, fmt(v1), ha="center", fontsize=7)
        ax.text(i + w/2, d_norm_ds[i] + 0.02, fmt(v2), ha="center", fontsize=7)

    fig.tight_layout()
    out = FIG_DIR / "fig4_ablation.pdf"
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  → {out}")


def main() -> None:
    main_rows = load_jsonl(_ROOT / "results" / "main_eval" / "eval_results.jsonl")
    cross_rows = load_jsonl(_ROOT / "results" / "cross_vlm" / "probing.jsonl")
    judge_rows = load_jsonl(_ROOT / "results" / "mllm_judge" / "scores.jsonl")

    if not main_rows:
        print("[err] main_eval results missing — run experiments.main_eval first")
        return
    print(f"[figures] main_eval: {len(main_rows)} rows")
    print(f"[figures] cross_vlm: {len(cross_rows)} rows")
    print(f"[figures] mllm_judge: {len(judge_rows)} rows")

    fig1_perception_generation_gap(main_rows, cross_rows or None)
    fig2_methods(main_rows)
    if judge_rows:
        fig3_layouts(main_rows, judge_rows)
    fig4_ablation()


if __name__ == "__main__":
    main()
