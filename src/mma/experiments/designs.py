"""Experiment designs for a two-sided marketplace and their estimators. Shipping code: the platform
uses these to run real experiments; the study measures how wrong each one is against the truth."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..matching.policies import Capacity
from ..shared.config import load


def _h(*parts) -> float:
    return int(hashlib.blake2b("|".join(map(str, parts)).encode(), digest_size=8).hexdigest(), 16) / 2**64


@dataclass
class Assignment:
    arms: np.ndarray
    clusters: np.ndarray
    views: list[Capacity]


def assign(design: str, requests: pd.DataFrame, caps: dict[int, int], salt: int, regions: list[str] | None = None) -> Assignment:
    """arms (0 = control, 1 = treatment), the cluster of each request (for standard errors) and the
    capacity views of the two arms."""
    d = load("experiments")["designs"][design]
    share = load("experiments")["treatment_share"]
    rid = requests["request_id"].to_numpy()
    if d["unit"] == "request":
        arms = np.array([_h(design, salt, r) < share for r in rid], dtype=int)
        clusters = rid
    elif d["unit"] == "region":
        reg = requests["region"].to_numpy()
        names = regions or sorted(set(map(str, reg)))
        on = {str(x): int(_h(design, salt, x) < share) for x in names}
        arms = np.array([on[str(x)] for x in reg], dtype=int)
        clusters = reg
    else:
        period = np.floor(requests["ts"].to_numpy() / d["period_days"]).astype(int)
        arms = np.array([int(_h(design, salt, p) < share) for p in period], dtype=int)
        clusters = period
    if d.get("split_capacity"):
        c0, c1 = {}, {}
        for p, k in caps.items():
            half = k // 2
            extra = k - 2 * half
            give = int(_h("split", salt, p) < share) if extra else 0
            c1[p] = half + give * extra
            c0[p] = k - c1[p]
        views = [Capacity(c0), Capacity(c1)]
    else:
        shared = Capacity(dict(caps))
        views = [shared, shared]
    return Assignment(arms, clusters, views)


def estimate(df: pd.DataFrame, arms: np.ndarray, clusters: np.ndarray, metric: str, alpha: float = 0.05) -> dict:
    """Difference in means (treatment - control) with a cluster-robust standard error (clusters are
    requests for request-level designs, regions or periods otherwise)."""
    y = df[metric].to_numpy(float)
    t = arms == 1
    m1, m0 = y[t].mean(), y[~t].mean()
    # cluster-robust variance of each arm mean: sum over clusters of squared residual totals / n^2
    var = 0.0
    for mask, m in ((t, m1), (~t, m0)):
        r = pd.Series(y[mask] - m).groupby(clusters[mask]).sum()
        g = len(r)
        n = mask.sum()
        var += (g / max(1, g - 1)) * float((r**2).sum()) / n**2
    se = var**0.5
    from scipy.stats import norm

    z = norm.ppf(1 - alpha / 2)
    est = m1 - m0
    return {
        "estimate": float(est),
        "se": float(se),
        "lo": float(est - z * se),
        "hi": float(est + z * se),
        "control_mean": float(m0),
    }
