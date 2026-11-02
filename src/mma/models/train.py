"""Trains the contact and win models on time-ordered slices, calibrates them, and logs everything to
MLflow (parameters, metrics, reliability tables, the scorer). Promotion to the champion alias is a
separate, gated step (mma.models.registry)."""

from __future__ import annotations

import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from ..features.store import CATEGORICAL, FEATURES
from ..shared.config import load
from .metrics import reliability, summary
from .scorer import Calibrated, Scorer


def slices(df: pd.DataFrame, label: str, cutoff: float, cfg: dict) -> dict[str, pd.DataFrame]:
    c = cfg[label]
    matured = cutoff - c["maturity_days"]
    a = matured - c["slices"]["train_end"]
    b = matured - c["slices"]["calib_end"]
    d = df[df.ts >= cfg["features_from_day"]]
    return {"train": d[d.ts < a], "calib": d[(d.ts >= a) & (d.ts < b)], "test": d[(d.ts >= b) & (d.ts < matured)]}


def fit_one(df: pd.DataFrame, label: str, cutoff: float, cfg: dict) -> tuple[Calibrated, dict]:
    s = slices(df, label, cutoff, cfg)
    target = "contacted" if label == "contact" else "won"
    X = {k: v[FEATURES].to_numpy(float) for k, v in s.items()}
    y = {k: v[target].to_numpy(float) for k, v in s.items()}
    params = dict(cfg["lightgbm"])
    dtrain = lgb.Dataset(X["train"], y["train"], feature_name=FEATURES, categorical_feature=CATEGORICAL, free_raw_data=False)
    dval = lgb.Dataset(X["calib"], y["calib"], reference=dtrain)
    booster = lgb.train(
        params,
        dtrain,
        num_boost_round=cfg["rounds"],
        valid_sets=[dval],
        callbacks=[lgb.early_stopping(cfg["early_stopping"], verbose=False)],
    )
    raw = {k: booster.predict(X[k], num_threads=1) for k in X}
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(raw["calib"], y["calib"])
    model = Calibrated(booster, iso.X_thresholds_.astype(float), iso.y_thresholds_.astype(float))
    p_test = model.predict(X["test"])
    metrics = {
        "rows": {k: int(len(v)) for k, v in s.items()},
        "best_iteration": int(booster.best_iteration or cfg["rounds"]),
        "test": summary(y["test"], p_test, cfg["ece_bins"]),
        "test_uncalibrated": summary(y["test"], raw["test"], cfg["ece_bins"]),
        "reliability": reliability(y["test"], p_test, cfg["ece_bins"]),
        "importance": dict(zip(FEATURES, booster.feature_importance("gain").round(1).tolist(), strict=True)),
        "slices": {k: [float(v.ts.min()), float(v.ts.max())] for k, v in s.items() if len(v)},
    }
    return model, metrics


def train(df: pd.DataFrame, cutoff: float) -> tuple[Scorer, dict]:
    cfg = load("models")
    contact, mc = fit_one(df, "contact", cutoff, cfg)
    win, mw = fit_one(df, "win", cutoff, cfg)
    return Scorer(contact, win, FEATURES), {"contact": mc, "win": mw, "cutoff": cutoff}


def save_local(scorer: Scorer, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(scorer, f)


def load_local(path: Path) -> Scorer:
    with open(path, "rb") as f:
        return pickle.load(f)


def flat_metrics(m: dict) -> dict[str, float]:
    out = {}
    for model in ("contact", "win"):
        for k, v in m[model]["test"].items():
            if isinstance(v, float | int) and not np.isnan(v):
                out[f"{model}_{k}"] = float(v)
        out[f"{model}_ece_uncalibrated"] = float(m[model]["test_uncalibrated"]["ece"])
    return out
