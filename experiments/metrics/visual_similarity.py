"""Visual fidelity metrics: CLIP score, LPIPS.

All compare a reference PNG against a generated PNG (rendered output).
Vocabulary-free, established in Design2Code / SlidesBench / SlideCoder.

NOTE: SSIM was removed from the default metric set after the paper's
design2code review concluded it is not informative for slide rendering
(JPEG-noise-era pixel metric, "blank canvas" attack, alignment-brittle).
The legacy `ssim_score` helper below is kept only for backwards-compat
with old result-loading code that may still expect the field.
"""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache

import numpy as np
from PIL import Image


# ─────────────────────────────────────────────────────────────────
# SSIM — pixel structural similarity (existing path)
# ─────────────────────────────────────────────────────────────────
def ssim_score(ref_png: Path | str, gen_png: Path | str) -> float:
    from skimage.metrics import structural_similarity as ssim
    ref = np.array(Image.open(ref_png).convert("L").resize((1280, 720)))
    gen = np.array(Image.open(gen_png).convert("L").resize((1280, 720)))
    return float(ssim(ref, gen))


# ─────────────────────────────────────────────────────────────────
# CLIP — semantic visual similarity (open_clip ViT-B/32)
# ─────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _clip_model():
    import open_clip, torch
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="laion2b_s34b_b79k"
    )
    model.eval()
    return model, preprocess


def clip_score(ref_png: Path | str, gen_png: Path | str) -> float:
    """Cosine similarity between CLIP image embeddings (semantic level)."""
    import torch
    model, preprocess = _clip_model()
    with torch.no_grad():
        ref_t = preprocess(Image.open(ref_png).convert("RGB")).unsqueeze(0)
        gen_t = preprocess(Image.open(gen_png).convert("RGB")).unsqueeze(0)
        ref_emb = model.encode_image(ref_t)
        gen_emb = model.encode_image(gen_t)
        ref_emb = ref_emb / ref_emb.norm(dim=-1, keepdim=True)
        gen_emb = gen_emb / gen_emb.norm(dim=-1, keepdim=True)
        sim = (ref_emb @ gen_emb.T).item()
    return float(sim)


# ─────────────────────────────────────────────────────────────────
# LPIPS — perceptual similarity (AlexNet deep features)
# ─────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _lpips_model():
    import lpips, torch
    model = lpips.LPIPS(net="alex", verbose=False)
    model.eval()
    return model


def lpips_score(ref_png: Path | str, gen_png: Path | str) -> float:
    """LPIPS distance — lower = more perceptually similar."""
    import torch, torchvision.transforms as T
    model = _lpips_model()
    tx = T.Compose([T.Resize((256, 256)), T.ToTensor(), T.Normalize([0.5]*3, [0.5]*3)])
    ref_t = tx(Image.open(ref_png).convert("RGB")).unsqueeze(0)
    gen_t = tx(Image.open(gen_png).convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        d = model(ref_t, gen_t).item()
    return float(d)


def all_visual_metrics(ref_png: Path | str, gen_png: Path | str) -> dict:
    """CLIP + LPIPS only. SSIM intentionally excluded — see module docstring."""
    return {
        "clip": clip_score(ref_png, gen_png),
        "lpips": lpips_score(ref_png, gen_png),
    }


def _self_test():
    import sys
    if len(sys.argv) < 3:
        print("usage: python -m experiments.metrics.visual_similarity <ref.png> <gen.png>")
        return
    print(all_visual_metrics(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    _self_test()
