"""Statistical analysis helpers: Wilcoxon, Kendall τ, Cohen κ, bootstrap CI."""
from __future__ import annotations

import math
from typing import Iterable


def paired_wilcoxon(a: list[float], b: list[float]) -> dict:
    """Paired Wilcoxon signed-rank test."""
    try:
        from scipy.stats import wilcoxon
    except ImportError:
        return {"error": "pip install scipy"}
    if len(a) != len(b) or len(a) < 2:
        return {"error": "need paired samples, n>=2"}
    stat, p = wilcoxon(a, b)
    return {"W": float(stat), "p": float(p), "n": len(a)}


def kendall_tau(a: list[float], b: list[float]) -> dict:
    try:
        from scipy.stats import kendalltau
    except ImportError:
        return {"error": "pip install scipy"}
    tau, p = kendalltau(a, b)
    return {"tau": float(tau), "p": float(p), "n": len(a)}


def cohen_kappa(rater_a: list, rater_b: list) -> dict:
    try:
        from sklearn.metrics import cohen_kappa_score
    except ImportError:
        return {"error": "pip install scikit-learn"}
    return {"kappa": float(cohen_kappa_score(rater_a, rater_b)), "n": len(rater_a)}


def bootstrap_ci(values: Iterable[float], n_boot: int = 1000, alpha: float = 0.05) -> dict:
    import random

    vs = list(values)
    if not vs:
        return {"error": "empty"}
    boots = []
    for _ in range(n_boot):
        sample = [random.choice(vs) for _ in vs]
        boots.append(sum(sample) / len(sample))
    boots.sort()
    lo = boots[int(n_boot * alpha / 2)]
    hi = boots[int(n_boot * (1 - alpha / 2))]
    mean = sum(vs) / len(vs)
    return {"mean": mean, "ci_lo": lo, "ci_hi": hi, "n": len(vs), "n_boot": n_boot}
