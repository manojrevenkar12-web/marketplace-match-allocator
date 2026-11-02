"""Monitoring: feature drift (population stability index) between the training window and the latest
days, and calibration of the champion on the newest matured labels."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..features.store import FEATURES
from ..models.metrics import summary


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    qs = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(qs) < 3:
        return 0.0
    e = np.histogram(np.clip(expected, qs[0], qs[-1]), qs)[0] / len(expected)
    a = np.histogram(np.clip(actual, qs[0], qs[-1]), qs)[0] / max(1, len(actual))
    e = np.clip(e, 1e-4, None)
    a = np.clip(a, 1e-4, None)
    return float(np.sum((a - e) * np.log(a / e)))


def report(
    pairs: pd.DataFrame,
    scorer,
    train_until: float,
    recent_days: float,
    now: float,
    thresholds: dict,
    days_per_month: float = 30.0,
) -> dict:
    """Drift of the last `recent_days` against the same days of the month in the training window:
    capacity fills up during a month, so month-end features differ from month averages by design."""
    cur = pairs[(pairs.ts >= now - recent_days) & (pairs.ts < now)]
    dom_lo = (now - recent_days) % days_per_month
    dom_hi = dom_lo + recent_days
    dom = pairs.ts % days_per_month
    ref = pairs[
        (pairs.ts < train_until)
        & (((dom >= dom_lo) & (dom < dom_hi)) | ((dom + days_per_month >= dom_lo) & (dom + days_per_month < dom_hi)))
    ]
    drift = {f: psi(ref[f].to_numpy(float), cur[f].to_numpy(float)) for f in FEATURES}
    out = {"psi": drift, "drifted": [f for f, v in drift.items() if v > thresholds["psi"]], "rows_recent": int(len(cur))}
    # calibration on the newest leads whose contact label has matured
    mat = pairs[(pairs.ts >= now - recent_days - 3) & (pairs.ts < now - 3)]
    if len(mat) > 200:
        pc, _ = scorer.predict(mat[FEATURES].to_numpy(float))
        s = summary(mat["contacted"].to_numpy(float), pc)
        out["contact_calibration"] = s
        out["calibration_alert"] = s["ece"] > thresholds["ece"]
    return out
