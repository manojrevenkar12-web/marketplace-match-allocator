"""Calibration and ranking metrics."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_auc_score


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error with equal-mass bins."""
    order = np.argsort(p)
    chunks = np.array_split(order, bins)
    n = len(p)
    return float(sum(len(c) / n * abs(y[c].mean() - p[c].mean()) for c in chunks if len(c)))


def reliability(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict]:
    order = np.argsort(p)
    return [
        {"predicted": float(p[c].mean()), "observed": float(y[c].mean()), "n": int(len(c))}
        for c in np.array_split(order, bins)
        if len(c)
    ]


def summary(y: np.ndarray, p: np.ndarray, bins: int = 10) -> dict:
    y = y.astype(float)
    eps = 1e-6
    pc = np.clip(p, eps, 1 - eps)
    return {
        "n": int(len(y)),
        "base_rate": float(y.mean()),
        "auc": float(roc_auc_score(y, p)) if 0 < y.mean() < 1 else float("nan"),
        "brier": float(np.mean((p - y) ** 2)),
        "logloss": float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc))),
        "ece": ece(y, p, bins),
        "mean_predicted": float(p.mean()),
    }
