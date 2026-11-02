"""Rebuilds the online feature store from raw logs by replaying them in time order: the backfill path
when a service starts, and the reference for the training/serving parity test."""

from __future__ import annotations

import heapq
from pathlib import Path

import numpy as np
import pandas as pd

from ..shared.types import PartnerSettings, RequestObs
from .store import FEATURES, FeatureStore, eligible


def settings_for(ps: pd.DataFrame, month: int) -> dict[int, PartnerSettings]:
    sub = ps[ps.month == month]
    return {
        int(r.partner_id): PartnerSettings(
            int(r.partner_id),
            r.home_region,
            frozenset(r.categories.split("|")),
            frozenset(r.regions.split("|")),
            int(r.monthly_cap),
            float(r.pause_from),
            float(r.pause_to),
            float(r.signup_day),
        )
        for r in sub.itertuples()
    }


def replay(raw_dir: Path, collect: bool = True, days_per_month: float = 30.0) -> tuple[FeatureStore, pd.DataFrame, dict]:
    """Replays raw logs. Returns the warm store, the online features of every logged lead (when
    collect) and the month's capacity use at the end."""
    req = pd.read_parquet(raw_dir / "requests.parquet").sort_values("ts", kind="stable")
    matches = pd.read_parquet(raw_dir / "matches.parquet")
    events = pd.read_parquet(raw_dir / "events.parquet")
    ps = pd.read_parquet(raw_dir / "partner_settings.parquet")
    by_req = matches.groupby("request_id")["partner_id"].apply(list).to_dict()
    lead_ts = dict(zip(zip(matches.request_id, matches.partner_id, strict=True), matches.ts, strict=True))
    q = [
        (float(e.ts), i, e.kind, int(e.partner_id), float(lead_ts[(e.request_id, e.partner_id)]))
        for i, e in enumerate(events.itertuples())
    ]
    heapq.heapify(q)
    store: FeatureStore | None = None
    month = -1
    used: dict[int, int] = {}
    cap: dict[int, int] = {}
    rows: list[np.ndarray] = []
    keys: list[tuple[int, int]] = []
    for r in req.itertuples(index=False):
        m = int(r.ts // days_per_month)
        if m != month:
            month = m
            s = settings_for(ps, m)
            store = FeatureStore(s) if store is None else (store.update_settings(s) or store)
            used = {}
            cap = {p: x.monthly_cap for p, x in s.items()}
        while q and q[0][0] < r.ts:
            ts, _, kind, pid, lt = heapq.heappop(q)
            if kind == "contacted":
                store.record_contact(pid, lt, ts)
            else:
                store.record_win(pid, ts)
        obs = RequestObs(int(r.request_id), float(r.ts), r.region, r.category, r.budget, r.timeframe, bool(r.qualified))
        chosen = by_req.get(r.request_id, [])
        if collect and chosen:
            cands = eligible(store, obs, used, cap)
            X = store.features(obs, cands, month * days_per_month)
            idx = {p: i for i, p in enumerate(cands)}
            for p in chosen:
                rows.append(X[idx[p]] if p in idx else np.full(len(FEATURES), np.nan))
                keys.append((obs.request_id, p))
        for p in chosen:
            used[p] = used.get(p, 0) + 1
            store.record_lead(p, obs.ts)
        store.record_request(obs)
    df = pd.DataFrame(rows, columns=FEATURES)
    if keys:
        df.insert(0, "partner_id", [k[1] for k in keys])
        df.insert(0, "request_id", [k[0] for k in keys])
    return store, df, {"month": month, "used": used}
