"""The online feature store: point-in-time features for (request, partner) pairs at serving time.

Every feature is a count or sum over event timestamps in a window ending at the request time, so it
can be maintained with sorted arrays (bisect) online and written as window aggregates in SQL for
training (dbt/models/features). The definitions live in config/features.yaml; the parity test checks
that both implementations agree on logged requests.
"""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from ..shared.config import load
from ..shared.geo import distance
from ..shared.types import BUDGETS, CATEGORIES, TIMEFRAMES, PartnerSettings, RequestObs

FEATURES = [
    "category",
    "budget",
    "timeframe",
    "qualified",
    "hour",
    "distance",
    "partner_cap",
    "partner_fill",
    "partner_leads_30d",
    "partner_contact_rate",
    "partner_win_rate",
    "partner_response_hours",
    "partner_tenure_days",
    "partner_ncats",
    "region_pressure",
    "n_candidates",
]
CATEGORICAL = ["category", "budget", "timeframe"]


@dataclass
class _Partner:
    leads: list[float] = field(default_factory=list)
    contacts: list[float] = field(default_factory=list)
    delay_cum: list[float] = field(default_factory=lambda: [0.0])
    wins: list[float] = field(default_factory=list)


def _count(xs: list[float], lo: float, hi: float) -> int:
    return bisect_left(xs, hi) - bisect_left(xs, lo)


class FeatureStore:
    def __init__(self, settings: dict[int, PartnerSettings]):
        self.cfg = load("features")
        self.settings = settings
        self.p: dict[int, _Partner] = defaultdict(_Partner)
        self.requests: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._supply: dict[tuple[str, str], int] = {}
        self.update_settings(settings)

    def update_settings(self, settings: dict[int, PartnerSettings]) -> None:
        self.settings = settings
        supply: dict[tuple[str, str], int] = defaultdict(int)
        index: dict[tuple[str, str], list[int]] = defaultdict(list)
        for s in settings.values():
            for r in s.regions:
                for c in s.categories:
                    supply[(r, c)] += s.monthly_cap
                    index[(r, c)].append(s.partner_id)
        self._supply = dict(supply)
        self.index = {k: sorted(v) for k, v in index.items()}

    # events arrive in timestamp order per kind
    def record_request(self, req: RequestObs) -> None:
        self.requests[(req.region, req.category)].append(req.ts)

    def record_lead(self, pid: int, ts: float) -> None:
        self.p[pid].leads.append(ts)

    def record_contact(self, pid: int, lead_ts: float, contact_ts: float) -> None:
        p = self.p[pid]
        p.contacts.append(contact_ts)
        p.delay_cum.append(p.delay_cum[-1] + (contact_ts - lead_ts) * 24.0)

    def record_win(self, pid: int, win_ts: float) -> None:
        self.p[pid].wins.append(win_ts)

    def leads_since(self, pid: int, since: float, until: float) -> int:
        return _count(self.p[pid].leads, since, until)

    def features(self, req: RequestObs, candidates: list[int], month_start: float) -> np.ndarray:
        c = self.cfg
        pr = c["prior"]
        t = req.ts
        out = np.zeros((len(candidates), len(FEATURES)))
        demand = _count(self.requests[(req.region, req.category)], t - c["demand_window_days"], t)
        supply = self._supply.get((req.region, req.category), 0)
        pressure = demand * (30.0 / c["demand_window_days"]) / supply if supply else 99.0
        for k, pid in enumerate(candidates):
            s = self.settings[pid]
            p = self.p[pid]
            leads_ctr = _count(p.leads, t - c["lead_window_days"] - c["lead_lag_days"], t - c["lead_lag_days"])
            contacts = _count(p.contacts, t - c["lead_window_days"], t)
            i0 = bisect_left(p.contacts, t - c["response_window_days"])
            i1 = bisect_left(p.contacts, t)
            delay_sum = p.delay_cum[i1] - p.delay_cum[i0]
            wins = _count(p.wins, t - c["win_window_days"], t)
            leads_win = _count(p.leads, t - c["win_lead_from_days"], t - c["win_lead_to_days"])
            out[k] = [
                CATEGORIES.index(req.category),
                BUDGETS.index(req.budget),
                TIMEFRAMES.index(req.timeframe),
                float(req.qualified),
                (t % 1.0) * 24.0,
                distance(s.home_region, req.region),
                s.monthly_cap,
                _count(p.leads, month_start, t) / s.monthly_cap,
                _count(p.leads, t - 30, t),
                (contacts + pr["contact_rate"] * pr["contact_weight"]) / (leads_ctr + pr["contact_weight"]),
                (wins + pr["win_rate"] * pr["win_weight"]) / (leads_win + pr["win_weight"]),
                (delay_sum + pr["response_hours"] * 2) / ((i1 - i0) + 2),
                t - s.signup_day,
                len(s.categories),
                pressure,
                len(candidates),
            ]
        return out


def eligible(store: FeatureStore, req: RequestObs, used: dict[int, int], cap: dict[int, int]) -> list[int]:
    """Partners who serve the region and category, are not paused, and have capacity left (arm view)."""
    return [
        pid
        for pid in store.index.get((req.region, req.category), [])
        if not store.settings[pid].paused(req.ts) and used.get(pid, 0) < cap.get(pid, 0)
    ]
