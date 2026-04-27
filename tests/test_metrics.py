"""Unit tests for the standard evaluation metrics.

Validates each metric on synthetic inputs with known correct answers, so
result anomalies in main_eval can be quickly attributed to either the
methods or the metric implementation.

Run: python -m tests.test_metrics
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from experiments.metrics.position import position_alignment, _bbox_iou
from experiments.metrics.structural import block_match, element_iou
from experiments.probing.layer_tree import (
    LayerNode, layer_recall, lted, parse_html_tree, parse_perception_response,
)


def _approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


def test_bbox_iou_identical() -> None:
    a = {"x": 0, "y": 0, "w": 100, "h": 100}
    assert _approx(_bbox_iou(a, a), 1.0), "identical IoU should be 1.0"


def test_bbox_iou_disjoint() -> None:
    a = {"x": 0, "y": 0, "w": 100, "h": 100}
    b = {"x": 200, "y": 200, "w": 100, "h": 100}
    assert _approx(_bbox_iou(a, b), 0.0), "disjoint IoU should be 0.0"


def test_bbox_iou_half_overlap() -> None:
    a = {"x": 0, "y": 0, "w": 100, "h": 100}
    b = {"x": 50, "y": 0, "w": 100, "h": 100}
    # intersection = 50×100 = 5000, union = 100×100 + 100×100 - 5000 = 15000
    assert _approx(_bbox_iou(a, b), 5000 / 15000)


def test_block_match_perfect() -> None:
    blocks = [{"x": 0, "y": 0, "w": 50, "h": 50},
              {"x": 100, "y": 100, "w": 50, "h": 50}]
    assert _approx(block_match(blocks, blocks), 1.0), "perfect match should F1=1.0"


def test_block_match_disjoint() -> None:
    a = [{"x": 0, "y": 0, "w": 50, "h": 50}]
    b = [{"x": 500, "y": 500, "w": 50, "h": 50}]
    assert _approx(block_match(a, b), 0.0), "disjoint blocks should F1=0.0"


def test_position_alignment_perfect() -> None:
    blocks = [{"x": 0, "y": 0, "w": 50, "h": 50},
              {"x": 100, "y": 100, "w": 50, "h": 50}]
    assert _approx(position_alignment(blocks, blocks, 1280, 720), 1.0), \
        "perfect overlap should give Position=1.0"


def test_position_alignment_offset() -> None:
    a = [{"x": 0, "y": 0, "w": 50, "h": 50}]
    b = [{"x": 10, "y": 0, "w": 50, "h": 50}]
    # IoU = 40*50 / (50*50 + 50*50 - 40*50) = 2000/3000 = 0.667 (above 0.5)
    # d = 10, D = sqrt(1280²+720²) = 1469.34
    # score = 1 - 10/1469.34 ≈ 0.9932
    score = position_alignment(a, b, 1280, 720)
    assert 0.99 < score < 1.0, f"small offset should give ~0.99, got {score}"


def test_layer_recall_perfect() -> None:
    tree = [LayerNode(z=0, type="background"), LayerNode(z=1, type="card")]
    assert _approx(layer_recall(tree, tree), 1.0)


def test_layer_recall_partial() -> None:
    ref = [LayerNode(z=0, type="background"), LayerNode(z=1, type="card"),
           LayerNode(z=2, type="value")]
    gen = [LayerNode(z=0, type="background"), LayerNode(z=1, type="card")]
    # 2 of 3 ref types present
    assert _approx(layer_recall(ref, gen), 2 / 3)


def test_lted_identical() -> None:
    tree = [LayerNode(z=0, type="background", count=1),
            LayerNode(z=1, type="card", count=3)]
    assert _approx(lted(tree, tree), 0.0)


def test_lted_disjoint() -> None:
    a = [LayerNode(z=0, type="background", count=1)]
    b = [LayerNode(z=20, type="icon", count=5)]
    # different bands, different types — full symmetric difference
    # multi_a = {(back, background): 1}, multi_b = {(front, icon): 5}
    # diff = 1 + 5 = 6, total = 1 + 5 = 6 → lted = 1.0
    assert _approx(lted(a, b), 1.0)


def test_parse_perception_basic() -> None:
    text = """z=0: type=background, count=1, label=dark
    z=1: type=card, count=3, label=glass
    z=2: type=value, count=3, label=numbers"""
    tree = parse_perception_response(text)
    assert len(tree) == 3
    assert tree[0].z == 0 and tree[0].type == "background"
    assert tree[1].count == 3


def test_parse_html_tree_basic() -> None:
    html = """<style>.card-1 {z-index:10}</style>
    <div class="bg-base" style="z-index:0">bg</div>
    <div class="card-wrap-1" style="position:absolute;z-index:10">
      <div class="card-1">x</div>
    </div>
    <div class="card-icon" style="z-index:30">i</div>"""
    tree = parse_html_tree(html)
    types = {n.type for n in tree}
    assert "background" in types
    assert "card" in types
    assert "icon" in types


# ────────────────────────────────────────────────────────────────────────────
def main() -> None:
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    print(f"[tests] running {len(tests)} metric tests")
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
        except AssertionError as e:
            print(f"  ✗ {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {fn.__name__}: {type(e).__name__}: {e}")
            failed += 1
    if failed:
        print(f"\n[tests] {failed}/{len(tests)} FAILED")
        sys.exit(1)
    print(f"\n[tests] all {len(tests)} passed")


if __name__ == "__main__":
    main()
