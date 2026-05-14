"""Re-compute LTED, layer_recall, n_*_layers using the SVG-aware parser.

Only updates the LTED columns in eval_results.jsonl / eval_summary.csv —
leaves render flags, OCR-based block metrics, CLIP, etc. untouched.

Run: PYTHONPATH=. python3 scripts/recompute_lted.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from experiments.metrics.lted import lted_from_perception_text

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "results" / "main_eval"
RAW_DIR = ROOT / "results" / "raw"
PERC_DIR = ROOT / "data" / "eval_dataset" / "perception"

BACKUP_SUFFIX = ".pre_svg_parser_backup"


def backup(path: Path) -> None:
    bk = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    if not bk.exists():
        bk.write_bytes(path.read_bytes())
        print(f"  backup → {bk.name}")


def recompute_jsonl(jsonl_path: Path) -> list[dict]:
    backup(jsonl_path)
    rows = [json.loads(l) for l in jsonl_path.read_text().splitlines() if l.strip()]
    updated = 0
    for row in rows:
        did = row["design_id"]
        method = row["method"]
        html_path = RAW_DIR / method / f"{did}_seed0.html"
        perc_path = PERC_DIR / f"{did}.txt"
        if not (html_path.exists() and perc_path.exists()):
            continue
        try:
            r = lted_from_perception_text(perc_path.read_text(), html_path.read_text())
            row["lted"] = r["lted"]
            row["layer_recall"] = r["layer_recall"]
            row["n_ref_layers"] = r["n_ref_layers"]
            row["n_gen_layers"] = r["n_gen_layers"]
            updated += 1
        except Exception as e:
            row["lted_err"] = str(e)
    with jsonl_path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  jsonl: updated {updated}/{len(rows)} rows")
    return rows


def recompute_csv(csv_path: Path, rows: list[dict]) -> None:
    backup(csv_path)
    # Preserve column order from the existing file
    existing = list(csv.DictReader(csv_path.open()))
    if not existing:
        return
    cols = list(existing[0].keys())
    # build lookup by (design_id, method)
    idx = {(r["design_id"], r["method"]): r for r in rows}
    for er in existing:
        key = (er["design_id"], er["method"])
        if key in idx:
            for col in ("lted", "layer_recall", "n_ref_layers", "n_gen_layers"):
                if col in cols and col in idx[key]:
                    er[col] = idx[key][col]
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for er in existing:
            w.writerow(er)
    print(f"  csv:   {len(existing)} rows rewritten")


def main():
    jsonl = EVAL_DIR / "eval_results.jsonl"
    csv_path = EVAL_DIR / "eval_summary.csv"
    print(f"[recompute] using parser: {Path(__file__).parent.parent}/experiments/probing/layer_tree.py")
    rows = recompute_jsonl(jsonl)
    recompute_csv(csv_path, rows)
    print("[recompute] done")


if __name__ == "__main__":
    main()
