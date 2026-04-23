"""Unified experiment runner.

Usage:
    python -m experiments.run --method layeragent --design design_10_stats_hero
    python -m experiments.run --method layeragent --ablation no_style_norm --design design_10_stats_hero
    python -m experiments.run --method single_pass --model gpt-5.4 --design design_10_stats_hero
    python -m experiments.run --method layeragent --all-designs
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from layeragent import LayerAgent, SUPPORTED_ABLATIONS
from layeragent.utils.common import load_active_specs, save_run

# Baselines registry
from baselines import single_pass, visual_cot, cot_h_rag, multi_model


BASELINES = {
    "single_pass": single_pass,
    "visual_cot": visual_cot,
    "cot_h_rag": cot_h_rag,
    "multi_model": multi_model,
}


def _run_layeragent(design_id: str, seed: int, model: str, ablation: str, vc: bool) -> tuple[str, float]:
    agent = LayerAgent(model=model, ablation=ablation, use_visual_critic=vc)
    t0 = time.time()
    html = agent.run(design_id, seed=seed)
    return html, time.time() - t0


def _run_baseline(name: str, design_id: str, seed: int, model: str) -> tuple[str, float]:
    mod = BASELINES[name]
    t0 = time.time()
    html = mod.run(design_id, seed=seed, model=model)
    return html, time.time() - t0


def method_label(method: str, ablation: str, vc: bool, model: str) -> str:
    if method == "layeragent":
        parts = ["layeragent"]
        if ablation != "none":
            parts.append(ablation)
        if vc:
            parts.append("vc")
        if model != "gpt-4o":
            parts.append(model.replace(".", "_"))
        return "-".join(parts)
    else:
        return f"{method}-{model.replace('.', '_')}" if model != "gpt-4o" else method


def main():
    p = argparse.ArgumentParser(description="LayerAgent unified runner")
    p.add_argument("--method", default="layeragent",
                   choices=["layeragent"] + list(BASELINES.keys()),
                   help="method to run")
    p.add_argument("--ablation", default="none", choices=SUPPORTED_ABLATIONS,
                   help="ablation flag (layeragent only)")
    p.add_argument("--visual-critic", action="store_true",
                   help="attach Visual Critic stage (layeragent only)")
    p.add_argument("--model", default="gpt-4o",
                   help="VLM model (gpt-4o | gpt-5.4 | claude-4.6-opus)")
    p.add_argument("--design", help="single slide id to run")
    p.add_argument("--all-designs", action="store_true",
                   help="run on all designs in data/slide_specs.jsonl")
    p.add_argument("--n-seeds", type=int, default=1, help="seed repetitions")
    p.add_argument("--out-dir", default=None, help="custom output dir")
    args = p.parse_args()

    if not args.design and not args.all_designs:
        p.error("--design or --all-designs required")

    if args.all_designs:
        specs = load_active_specs()
        design_ids = [s["id"] for s in specs]
    else:
        design_ids = [args.design]

    label = method_label(args.method, args.ablation, args.visual_critic, args.model)
    print(f"[run] method={label} ({len(design_ids)} design × {args.n_seeds} seeds)")

    for did in design_ids:
        for seed in range(args.n_seeds):
            tag = f"[{label}] {did} seed={seed}"
            print(f"{tag} ...", flush=True)
            try:
                if args.method == "layeragent":
                    html, dt = _run_layeragent(did, seed, args.model, args.ablation, args.visual_critic)
                else:
                    html, dt = _run_baseline(args.method, did, seed, args.model)
                save_run(label, did, seed, html)
                print(f"{tag} ✓ {dt:.1f}s len={len(html)}")
            except Exception as e:
                traceback.print_exc()
                print(f"{tag} ✗ {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
