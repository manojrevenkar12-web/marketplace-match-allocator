"""Matching policies. A policy sees the request, its eligible partners, the capacity view of its arm
and the feature store; it returns up to three partners. Policies never see the truth."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from ..features.store import FeatureStore
from ..shared.config import load
from ..shared.types import MAX_PARTNERS, RequestObs


@dataclass
class Capacity:
    """One arm's view of partner capacity this month."""

    cap: dict[int, int]
    used: dict[int, int] = field(default_factory=dict)

    def remaining(self, pid: int) -> int:
        return self.cap.get(pid, 0) - self.used.get(pid, 0)

    def take(self, pid: int) -> None:
        self.used[pid] = self.used.get(pid, 0) + 1


class Policy(Protocol):
    name: str

    def choose(
        self, req: RequestObs, candidates: list[int], cap: Capacity, store: FeatureStore, month_start: float
    ) -> list[int]: ...


def _tiebreak(rid: int, pid: int) -> float:
    return int(hashlib.blake2b(f"{rid}:{pid}".encode(), digest_size=8).hexdigest(), 16) / 2**64


class RuleBaseline:
    """The current logic, as rules: the eligible partners with the lowest share of their monthly volume
    used so far, ties broken at random. It spreads leads evenly and ignores quality."""

    name = "rules"

    def choose(self, req, candidates, cap, store, month_start):
        ranked = sorted(candidates, key=lambda p: (cap.used.get(p, 0) / max(1, cap.cap[p]), _tiebreak(req.request_id, p)))
        return ranked[:MAX_PARTNERS]


class Scorer(Protocol):
    def predict(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(p_contact, p_win) per row."""
        ...


class Pacer:
    """Bid prices per partner (euros per unit of its capacity) by dual descent on its monthly schedule (budget pacing): a partner's price
    rises while it uses its volume faster than the month elapses and falls back to zero when it is
    behind, so capacity is spread over the month but never left stranded. Shared by all model arms of
    one capacity view; updated every few simulated hours."""

    def __init__(self, cfg: dict, days_per_month: float = 30.0):
        self.cfg = cfg
        self.days = days_per_month
        self.bid: dict[int, float] = {}
        self.at = -1e9

    def refresh(self, t: float, cap: Capacity, store: FeatureStore, month_start: float) -> None:
        c = self.cfg["pacing"]
        step = c["recompute_hours"] / 24.0
        if t - self.at < step:
            return
        if t < month_start + step:
            self.bid = {}
        self.at = t
        elapsed = min(1.0, max(0.0, (t - month_start) / self.days))
        for p, k in cap.cap.items():
            if k <= 0:
                continue
            ahead = cap.used.get(p, 0) / k - elapsed
            self.bid[p] = max(0.0, min(c["max_bid_eur"], self.bid.get(p, 0.0) + c["step_eur"] * ahead))


class ModelPolicy:
    """Greedy set selection on a three-sided objective (revenue, homeowner, partner) in euros, with
    bid prices for scarce capacity. The homeowner term has diminishing returns: a second strong partner
    adds less than the first."""

    def __init__(self, scorer: Scorer, weights: str | dict | None = None, pacing: bool = True, name: str = "model"):
        self.cfg = load("matching")
        self.scorer = scorer
        w = weights or self.cfg["default_weights"]
        self.w = self.cfg["weights"][w] if isinstance(w, str) else w
        self.pacing = pacing
        self.name = name
        self.pacer = Pacer(self.cfg)

    def choose(self, req, candidates, cap, store, month_start):
        if not candidates:
            return []
        X = store.features(req, candidates, month_start)
        pc, pw = self.scorer.predict(X)
        c = self.cfg
        price = c["price"][req.category]
        hv, cv, margin = c["home_value"][req.category], c["contact_value"][req.category], c["partner_margin"][req.category]
        if self.pacing:
            self.pacer.refresh(req.ts, cap, store, month_start)
        bid = np.array([self.pacer.bid.get(p, 0.0) if self.pacing else 0.0 for p in candidates])
        base = self.w["revenue"] * price + self.w["partner"] * (pw * margin - price) - bid
        chosen: list[int] = []
        miss_win = 1.0
        miss_contact = 1.0
        left = list(range(len(candidates)))
        while left and len(chosen) < MAX_PARTNERS:
            gain = base[left] + self.w["homeowner"] * (hv * pw[left] * miss_win + cv * pc[left] * miss_contact)
            k = int(np.argmax(gain))
            if gain[k] <= 0:
                break
            j = left.pop(k)
            chosen.append(candidates[j])
            miss_win *= 1 - pw[j]
            miss_contact *= 1 - pc[j]
        return chosen
