"""The marketplace engine (truth side): plays requests in time order through one or more matching
policies, each with its own view of partner capacity, and resolves what happens after each match.
Shipping code (policies, feature store) only ever sees RequestObs, PartnerSettings and events."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..features.store import FeatureStore, eligible
from ..matching.policies import Capacity, Policy
from ..shared.types import BUDGETS, CATEGORIES, TIMEFRAMES, PartnerSettings, RequestObs
from .world import World


def settings_from(world: World, month: int) -> dict[int, PartnerSettings]:
    t = world.partner_table(month)
    return {
        int(r.partner_id): PartnerSettings(
            partner_id=int(r.partner_id),
            home_region=r.home_region,
            categories=frozenset(r.categories.split("|")),
            regions=frozenset(r.regions.split("|")),
            monthly_cap=int(r.monthly_cap),
            pause_from=float(r.pause_from),
            pause_to=float(r.pause_to),
            signup_day=float(r.signup_day),
        )
        for r in t.itertuples()
    }


def obs(world: World, row) -> RequestObs:
    return RequestObs(
        request_id=int(row.request_id),
        ts=float(row.ts),
        region=world.region_names[int(row.region)],
        category=CATEGORIES[int(row.category)],
        budget=BUDGETS[int(row.budget)],
        timeframe=TIMEFRAMES[int(row.timeframe)],
        qualified=bool(row.qualified),
    )


@dataclass
class Logs:
    requests: list[dict] = field(default_factory=list)
    matches: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    outcomes: list[dict] = field(default_factory=list)

    def frames(self) -> dict[str, pd.DataFrame]:
        return {k: pd.DataFrame(getattr(self, k)) for k in ("requests", "matches", "events", "outcomes")}


class Market:
    """One marketplace over consecutive months: a feature store that keeps learning and a queue of
    events (calls, wins) that arrive after the request they belong to."""

    def __init__(self, world: World, keep_logs: bool = True):
        self.world = world
        self.store: FeatureStore | None = None
        self.queue: list[tuple[float, int, str, int, float]] = []
        self.logs = Logs()
        self.keep_logs = keep_logs
        self._seq = 0

    def _deliver(self, t: float) -> None:
        q = self.queue
        while q and q[0][0] < t:
            ts, _, kind, pid, lead_ts = heapq.heappop(q)
            if kind == "contact":
                self.store.record_contact(pid, lead_ts, ts)
            else:
                self.store.record_win(pid, ts)

    def run(
        self,
        month: int,
        requests: pd.DataFrame,
        arms: np.ndarray,
        policies: list[Policy],
        views: list[Capacity],
        label: str = "",
    ) -> pd.DataFrame:
        """Plays one month. arms[i] picks the policy and capacity view for request i. Arms may share one
        Capacity object (they then compete for the same partner volume) or have their own (a budget split)."""
        w = self.world
        settings = settings_from(w, month)
        if self.store is None:
            self.store = FeatureStore(settings)
        else:
            self.store.update_settings(settings)
        month_start = month * w.days
        total_used: dict[int, int] = {}
        out = []
        for row, arm in zip(requests.itertuples(index=False), arms, strict=True):
            req = obs(w, row)
            self._deliver(req.ts)
            view = views[arm]
            cands = eligible(self.store, req, view.used, view.cap)
            chosen = policies[arm].choose(req, cands, view, self.store, month_start)
            pids = np.array(chosen, dtype=int)
            fill = np.array([total_used.get(p, 0) / settings[p].monthly_cap for p in chosen])
            rd = row._asdict()
            res = w.outcome(rd, pids, fill)
            price = w.price[int(row.category)]
            margin = w.margin[int(row.category)]
            for k, p in enumerate(chosen):
                view.take(p)
                total_used[p] = total_used.get(p, 0) + 1
                self.store.record_lead(p, req.ts)
                if res.contacted[k]:
                    heapq.heappush(self.queue, (float(res.contact_ts[k]), self._next(), "contact", p, req.ts))
                if res.won[k]:
                    heapq.heappush(self.queue, (float(res.win_ts[k]), self._next(), "win", p, req.ts))
                if self.keep_logs:
                    self.logs.matches.append(
                        {
                            "request_id": req.request_id,
                            "partner_id": p,
                            "ts": req.ts,
                            "rank": k,
                            "arm": int(arm),
                            "policy": policies[arm].name,
                            "price": price,
                        }
                    )
                    if res.contacted[k]:
                        self.logs.events.append(
                            {"request_id": req.request_id, "partner_id": p, "kind": "contacted", "ts": float(res.contact_ts[k])}
                        )
                    if res.won[k]:
                        self.logs.events.append(
                            {"request_id": req.request_id, "partner_id": p, "kind": "won", "ts": float(res.win_ts[k])}
                        )
            self.store.record_request(req)
            n = len(chosen)
            out.append(
                (
                    req.request_id,
                    int(arm),
                    int(row.region),
                    int(row.category),
                    req.ts,
                    n,
                    bool(res.contacted.any()) if n else False,
                    bool(res.project),
                    float(price * n),
                    float(margin * res.won.sum() - price * n),
                    int(res.won.sum()),
                )
            )
            if self.keep_logs:
                self.logs.requests.append(
                    {
                        "request_id": req.request_id,
                        "ts": req.ts,
                        "region": req.region,
                        "category": req.category,
                        "budget": req.budget,
                        "timeframe": req.timeframe,
                        "qualified": req.qualified,
                        "label": label,
                    }
                )
        df = pd.DataFrame(
            out,
            columns=[
                "request_id",
                "arm",
                "region",
                "category",
                "ts",
                "n_matched",
                "contacted",
                "project",
                "revenue",
                "partner_profit",
                "wins",
            ],
        )
        df["leads"] = df["n_matched"]
        if self.keep_logs:
            self.logs.outcomes.extend(df.assign(label=label).to_dict("records"))
        return df

    def _next(self) -> int:
        self._seq += 1
        return self._seq


def caps_of(world: World, month: int) -> dict[int, int]:
    return {int(i): int(c) for i, c in enumerate(world.partners.cap)}
