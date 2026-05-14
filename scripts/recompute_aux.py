"""Re-compute auxiliary LTED/Recall files using the SVG-aware parser:

  - results/tables/zexplicit_baseline.json  (N=10 design, single_pass_zexplicit)
  - results/cross_vlm/frontier_probing.jsonl (gpt-5.4, claude-4.6-opus on N=10)
  - experiments/probing/probing_results.jsonl (N=10 baseline tree_B1 + layeragent tree_B2)

All three use the same N=10 design slides whose HTML lives in
results/raw/{method}/<design_id>_seed0.html, so we re-parse from raw and
recompute trees/recall/LTED.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, stdev

from experiments.probing.layer_tree import (
    parse_html_tree, parse_perception_response, layer_recall, lted,
)

ROOT = Path(__file__).resolve().parent.parent
PERC_DIR = ROOT / "data" / "eval_dataset" / "perception"
RAW = ROOT / "results" / "raw"
DESIGN_IDS = [f"design_{i:02d}_" for i in range(1, 11)]


def n10_design_ids() -> list[str]:
    """The 10 design slides referenced in 5.1/5.4/B.2."""
    return sorted([f.stem for f in PERC_DIR.glob("design_*.txt")])


def backup(p: Path) -> None:
    bk = p.with_suffix(p.suffix + ".pre_svg_parser_backup")
    if not bk.exists() and p.exists():
        bk.write_bytes(p.read_bytes())
        print(f"  backup → {bk.name}")


def compute_for_method(method: str, designs: list[str]) -> dict:
    rows = []
    for did in designs:
        html_path = RAW / method / f"{did}_seed0.html"
        perc_path = PERC_DIR / f"{did}.txt"
        if not (html_path.exists() and perc_path.exists()):
            continue
        ref = parse_perception_response(perc_path.read_text())
        gen = parse_html_tree(html_path.read_text())
        rows.append({
            "design_id": did,
            "n_layers_gen": len(gen),
            "lted": lted(ref, gen),
            "layer_recall": layer_recall(ref, gen),
        })
    if not rows:
        return {"results": [], "aggregate": {}}
    lt_vals = [r["lted"] for r in rows]
    rec_vals = [r["layer_recall"] for r in rows]
    layers = [r["n_layers_gen"] for r in rows]
    return {
        "results": rows,
        "aggregate": {
            "lted_mean": mean(lt_vals),
            "lted_std": stdev(lt_vals) if len(lt_vals) > 1 else 0.0,
            "recall_mean": mean(rec_vals),
            "recall_std": stdev(rec_vals) if len(rec_vals) > 1 else 0.0,
            "avg_layers": mean(layers),
        },
    }


def main():
    designs = n10_design_ids()
    print(f"N=10 design slides: {len(designs)}")

    # 1) zexplicit baseline
    print("\n[1] single_pass_zexplicit")
    out = compute_for_method("single_pass_zexplicit", designs)
    path = ROOT / "results" / "tables" / "zexplicit_baseline.json"
    backup(path)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    a = out["aggregate"]
    print(f"  LTED={a['lted_mean']:.3f}±{a['lted_std']:.2f}  "
          f"Recall={a['recall_mean']:.3f}±{a['recall_std']:.2f}  "
          f"avg_layers={a['avg_layers']:.1f}")

    # 2) frontier probing (gpt-5.4, claude)
    print("\n[2] frontier_probing")
    frontier_rows = []
    for model_key, raw_dir in [("gpt-5.4", "single_pass_gpt_5_4"),
                               ("claude-4.6-opus", "single_pass_claude_4_6_opus")]:
        m_out = compute_for_method(raw_dir, designs)
        a = m_out["aggregate"]
        print(f"  {model_key:<20s} LTED={a['lted_mean']:.3f}  "
              f"Recall={a['recall_mean']:.3f}  gap={1-a['recall_mean']:.3f}  "
              f"layers={a['avg_layers']:.1f}")
        for r in m_out["results"]:
            r["model"] = model_key
            frontier_rows.append(r)
    fp = ROOT / "results" / "cross_vlm" / "frontier_probing.jsonl"
    backup(fp)
    # Preserve original keys: model, design_id, n_layers_gen, lted, layer_recall
    with fp.open("w") as f:
        for r in frontier_rows:
            f.write(json.dumps({
                "model": r["model"],
                "design_id": r["design_id"],
                "n_layers_gen": r["n_layers_gen"],
                "lted": r["lted"],
                "layer_recall": r["layer_recall"],
            }, ensure_ascii=False) + "\n")

    # 3) probing N=10 (single_pass as B1, layeragent as B2)
    print("\n[3] probing N=10 (single_pass vs layeragent)")
    pp = ROOT / "experiments" / "probing" / "probing_results.jsonl"
    backup(pp)
    out_rows = []
    for did in designs:
        perc = parse_perception_response((PERC_DIR / f"{did}.txt").read_text())
        b1_html = (RAW / "single_pass" / f"{did}_seed0.html")
        b2_html = (RAW / "layeragent" / f"{did}_seed0.html")
        if not (b1_html.exists() and b2_html.exists()):
            continue
        gen_b1 = parse_html_tree(b1_html.read_text())
        gen_b2 = parse_html_tree(b2_html.read_text())
        rec_b1 = layer_recall(perc, gen_b1)
        rec_b2 = layer_recall(perc, gen_b2)
        out_rows.append({
            "slide_id": did,
            "n_layers_A": len(perc),
            "n_layers_B1": len(gen_b1),
            "n_layers_B2": len(gen_b2),
            "tree_A": [n.to_dict() for n in perc],
            "tree_B1": [n.to_dict() for n in gen_b1],
            "tree_B2": [n.to_dict() for n in gen_b2],
            "recall_B1": rec_b1,
            "recall_B2": rec_b2,
            "lted_B1": lted(perc, gen_b1),
            "lted_B2": lted(perc, gen_b2),
            "gap_baseline": 1 - rec_b1,
            "gap_ours": 1 - rec_b2,
            "closure": rec_b2 - rec_b1,
        })
    with pp.open("w") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  rows: {len(out_rows)}")
    print(f"  avg n_layers: A(perception)={mean(r['n_layers_A'] for r in out_rows):.1f}  "
          f"B1(single_pass)={mean(r['n_layers_B1'] for r in out_rows):.1f}  "
          f"B2(layeragent)={mean(r['n_layers_B2'] for r in out_rows):.1f}")
    print(f"  avg recall: B1={mean(r['recall_B1'] for r in out_rows):.3f}  "
          f"B2={mean(r['recall_B2'] for r in out_rows):.3f}")
    print(f"  avg lted: B1={mean(r['lted_B1'] for r in out_rows):.3f}  "
          f"B2={mean(r['lted_B2'] for r in out_rows):.3f}")


if __name__ == "__main__":
    main()
