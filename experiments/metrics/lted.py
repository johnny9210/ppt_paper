"""LTED — Layer Tree Edit Distance.

Paper's novel metric. Compares the layer-stacking structure of a reference
slide (from VLM perception of the image) to the generated HTML's parsed
layer structure. Penalizes both missing layers and extra layers, and uses
z-band bucketing so back/mid/front bands matter rather than exact integers.

Wraps experiments/probing/layer_tree.py extractors so the same parsers are
used here as in the probing experiment (same metric across paper's two
analyses).
"""
from __future__ import annotations

from pathlib import Path

from experiments.probing.layer_tree import (
    PERCEPTION_PROMPT,
    parse_html_tree,
    parse_perception_response,
    layer_recall,
    lted as _multiset_lted,
)


def lted_from_perception_text(perception_text: str, generated_html: str) -> dict:
    """Compute LTED + recall given a VLM perception output and a generated HTML."""
    tree_ref = parse_perception_response(perception_text)
    tree_gen = parse_html_tree(generated_html)
    return {
        "lted": _multiset_lted(tree_ref, tree_gen),
        "layer_recall": layer_recall(tree_ref, tree_gen),
        "n_ref_layers": len(tree_ref),
        "n_gen_layers": len(tree_gen),
    }


def lted_from_files(perception_text_path: str | Path, html_path: str | Path) -> dict:
    perc = Path(perception_text_path).read_text()
    html = Path(html_path).read_text()
    return lted_from_perception_text(perc, html)


__all__ = [
    "PERCEPTION_PROMPT",
    "lted_from_perception_text",
    "lted_from_files",
]
