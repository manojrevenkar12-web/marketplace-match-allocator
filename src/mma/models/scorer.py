"""The scorer used at serving time: two LightGBM boosters, each followed by an isotonic calibration
map (stored as breakpoints and applied with np.interp, so scoring stays cheap per request)."""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np


@dataclass
class Calibrated:
    booster: lgb.Booster
    x: np.ndarray
    y: np.ndarray

    def raw(self, X: np.ndarray) -> np.ndarray:
        return self.booster.predict(X, num_threads=1)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.interp(self.raw(X), self.x, self.y)


@dataclass
class Scorer:
    contact: Calibrated
    win: Calibrated
    features: list[str]
    version: str = "local"

    def predict(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return self.contact.predict(X), self.win.predict(X)
