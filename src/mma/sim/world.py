"""THE TRUTH: a homeowner marketplace. Regions with uneven demand and supply, partners with capacity
and hidden quality, requests with hidden intent, and what happens after a match: which partners call,
in which order, and who (if anyone) wins the project. Only mma.sim and mma.evaluate import this.

What the platform can see is exported as tables (requests, partner settings, matches, events). Hidden
quantities (contact propensity, speed, skill, homeowner intent) never leave this module except as
outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from ..shared.config import CONFIG, deep_merge
from ..shared.rng import normal, uniform

DAY = 1.0


@cache
def _world_yaml() -> dict[str, Any]:
    with open(Path(CONFIG) / "world.yaml") as f:
        return yaml.safe_load(f)


def world_config(override: dict[str, Any] | None = None) -> dict[str, Any]:
    return deep_merge(_world_yaml(), override)


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class Partners:
    home: np.ndarray
    cats: np.ndarray  # bool [P, C]
    radius: np.ndarray
    serves: np.ndarray  # bool [P, R]
    cap: np.ndarray
    contact_logit: np.ndarray
    speed_hours: np.ndarray
    skill: np.ndarray
    signup_day: np.ndarray
    pause: dict[int, np.ndarray] = field(default_factory=dict)  # month -> [P, 2] paused day window (or -1)

    @property
    def n(self) -> int:
        return len(self.home)


@dataclass
class Outcome:
    """What happened after a request was matched to `partners` (aligned arrays)."""

    contacted: np.ndarray
    contact_ts: np.ndarray
    won: np.ndarray
    win_ts: np.ndarray
    project: bool


class World:
    def __init__(self, cfg: dict[str, Any], seed: int):
        self.cfg = cfg
        self.seed = seed
        rng = np.random.default_rng(seed)
        g = cfg["grid"]
        self.cols, self.rows = g["cols"], g["rows"]
        self.R = self.cols * self.rows
        self.region_names = [f"{10 + i:02d}" for i in range(self.R)]
        self.xy = np.array([(i % self.cols, i // self.cols) for i in range(self.R)])
        # a few metropolitan clusters plus noise
        centres = rng.choice(self.R, size=5, replace=False)
        d_c = np.min([np.max(np.abs(self.xy - self.xy[c]), axis=1) for c in centres], axis=0)
        logw = rng.normal(0, cfg["region_demand_sigma"], self.R) + 1.2 * np.exp(-d_c / 1.5)
        self.demand = np.exp(logw)
        self.demand /= self.demand.sum()
        supply = self.demand ** cfg["supply_elasticity"] * np.exp(rng.normal(0, 0.25, self.R))
        self.supply = supply / supply.sum()
        self.dist = np.max(np.abs(self.xy[:, None, :] - self.xy[None, :, :]), axis=2)

        self.cat_names = list(cfg["categories"])
        cats = cfg["categories"]
        self.C = len(self.cat_names)
        self.cat_share = np.array([cats[c]["share"] for c in self.cat_names])
        self.cat_share /= self.cat_share.sum()
        self.price = np.array([cats[c]["price"] for c in self.cat_names], dtype=float)
        self.intent = np.array([cats[c]["intent"] for c in self.cat_names], dtype=float)
        self.margin = np.array([cats[c]["margin"] for c in self.cat_names], dtype=float)
        self.partners = self._partners(rng)
        self.days = cfg["days_per_month"]

    # ------------------------------------------------------------------ partners
    def _partners(self, rng: np.random.Generator) -> Partners:
        c = self.cfg["partner"]
        P = self.cfg["partners"]
        home = rng.choice(self.R, size=P, p=self.supply)
        ncat = rng.integers(c["categories"][0], c["categories"][1] + 1, size=P)
        cats = np.zeros((P, self.C), dtype=bool)
        for i in range(P):
            cats[i, rng.choice(self.C, size=ncat[i], replace=False, p=self.cat_share)] = True
        rk = list(c["radius"])
        radius = rng.choice(np.array(rk, dtype=int), size=P, p=np.array([c["radius"][k] for k in rk], dtype=float))
        serves = self.dist[home] <= radius[:, None]
        cap = np.maximum(c["cap_min"], np.round(np.exp(np.log(c["cap_median"]) + rng.normal(0, c["cap_sigma"], P)))).astype(int)
        return Partners(
            home=home,
            cats=cats,
            radius=radius,
            serves=serves,
            cap=cap,
            contact_logit=rng.normal(c["contact_logit"]["mean"], c["contact_logit"]["sd"], P),
            speed_hours=np.exp(np.log(c["speed_hours"]["median"]) + rng.normal(0, c["speed_hours"]["sigma"], P)),
            skill=rng.normal(c["skill"]["mean"], c["skill"]["sd"], P),
            signup_day=-rng.integers(30, 1500, size=P).astype(float),
        )

    def pauses(self, month: int) -> np.ndarray:
        """[P, 2] paused day window within the month (absolute days), -1 when not paused."""
        if month not in self.partners.pause:
            rng = np.random.default_rng(self.seed * 1000 + month)
            P = self.partners.n
            out = -np.ones((P, 2))
            who = rng.random(P) < self.cfg["partner"]["pause_share"]
            start = rng.integers(0, self.days - 5, size=P)
            length = rng.integers(5, 13, size=P)
            base = month * self.days
            out[who, 0] = base + start[who]
            out[who, 1] = base + np.minimum(self.days, start[who] + length[who])
            self.partners.pause[month] = out
        return self.partners.pause[month]

    def partner_table(self, month: int) -> pd.DataFrame:
        """Partner settings as the platform sees them (what partners set in their account)."""
        p = self.partners
        pz = self.pauses(month)
        return pd.DataFrame(
            {
                "partner_id": np.arange(p.n),
                "month": month,
                "home_region": [self.region_names[h] for h in p.home],
                "categories": ["|".join(self.cat_names[j] for j in np.flatnonzero(p.cats[i])) for i in range(p.n)],
                "regions": ["|".join(self.region_names[r] for r in np.flatnonzero(p.serves[i])) for i in range(p.n)],
                "monthly_cap": p.cap,
                "pause_from": pz[:, 0],
                "pause_to": pz[:, 1],
                "signup_day": p.signup_day,
            }
        )

    # ------------------------------------------------------------------ requests
    def requests(self, month: int, stream: int = 0, scale: float = 1.0, demand_shift: np.ndarray | None = None) -> pd.DataFrame:
        """A month of requests. `stream` gives independent replications of the same month (ids differ, so
        outcome noise differs too)."""
        cfg = self.cfg["request"]
        rng = np.random.default_rng(self.seed * 7919 + month + 100_003 * stream)
        n = int(round(self.cfg["requests_per_month"] * scale))
        shape = np.array(cfg["daily_shape"])
        day_w = shape[np.arange(self.days) % 7]
        day = rng.choice(self.days, size=n, p=day_w / day_w.sum())
        hour = rng.uniform(7, 22, size=n)
        ts = month * self.days + day + hour / 24
        dw = self.demand if demand_shift is None else self.demand * demand_shift
        region = rng.choice(self.R, size=n, p=dw / dw.sum())
        cat = rng.choice(self.C, size=n, p=self.cat_share)
        b_names = list(cfg["budget"])
        budget = rng.choice(len(b_names), size=n, p=np.array([cfg["budget"][k] for k in b_names]))
        t_names = list(cfg["timeframe"])
        timeframe = rng.choice(len(t_names), size=n, p=np.array([cfg["timeframe"][k] for k in t_names]))
        qualified = rng.random(n) < cfg["qualified_share"]
        order = np.argsort(ts, kind="stable")
        df = pd.DataFrame(
            {
                "request_id": np.zeros(n, dtype=np.int64),
                "ts": ts[order],
                "region": region[order],
                "category": cat[order],
                "budget": budget[order],
                "timeframe": timeframe[order],
                "qualified": qualified[order],
            }
        )
        df["request_id"] = month * 1_000_000 + stream * 30_000 + np.arange(n)
        return df

    def intent_of(self, req: pd.Series | dict) -> float:
        cfg = self.cfg["request"]
        b = list(cfg["budget_intent"].values())[int(req["budget"])]
        t = list(cfg["timeframe_intent"].values())[int(req["timeframe"])]
        q = cfg["qualified_intent"] if bool(req["qualified"]) else 1.0
        noise = np.exp(cfg["intent_noise"] * normal(self.seed, int(req["request_id"]), 11))
        return float(min(0.95, self.intent[int(req["category"])] * b * t * q * noise))

    # ------------------------------------------------------------------ outcomes
    def outcome(self, req: dict, partners: np.ndarray, fill_at_delivery: np.ndarray) -> Outcome:
        """Who calls, when, and who wins. Deterministic in (seed, request, partner)."""
        o = self.cfg["outcome"]
        p = self.partners
        rid = int(req["request_id"])
        k = len(partners)
        if k == 0:
            return Outcome(np.zeros(0, bool), np.zeros(0), np.zeros(0, bool), np.zeros(0), False)
        overload = np.maximum(0.0, fill_at_delivery - 0.8)
        logit = (
            p.contact_logit[partners]
            + o["qualified_contact"] * float(req["qualified"])
            + o["asap_contact"] * float(int(req["timeframe"]) == 0)
            + o["overload_contact"] * overload / 0.2
        )
        contacted = uniform(self.seed, rid, partners, 1) < _sigmoid(logit)
        delay_h = p.speed_hours[partners] * np.exp(0.5 * normal(self.seed, rid, partners, 2))
        contact_ts = float(req["ts"]) + delay_h / 24
        dist = self.dist[p.home[partners], int(req["region"])]
        m = _sigmoid(p.skill[partners] - o["distance_penalty"] * dist + o["satisfy_bias"])
        satisfied = contacted & (uniform(self.seed, rid, partners, 3) < m)
        won = np.zeros(k, bool)
        win_ts = np.full(k, np.nan)
        project = False
        if satisfied.any() and uniform(self.seed, rid, 4) < self.intent_of(req):
            order = np.argsort(np.where(contacted, contact_ts, np.inf))
            rank = np.empty(k, int)
            rank[order] = np.arange(k)
            bonus = np.where(rank == 0, o["first_contact_bonus"], np.where(rank == 1, o["second_contact_bonus"], 0.0))
            gumbel = -np.log(-np.log(np.clip(uniform(self.seed, rid, partners, 5), 1e-12, 1 - 1e-12)))
            score = np.where(satisfied, p.skill[partners] + bonus + gumbel, -np.inf)
            w = int(np.argmax(score))
            won[w] = True
            lo, hi = o["win_delay_days"]
            win_ts[w] = float(req["ts"]) + lo + (hi - lo) * uniform(self.seed, rid, 6)
            project = True
        return Outcome(contacted, np.where(contacted, contact_ts, np.nan), won, win_ts, project)

    def true_scores(self, req: dict, partners: np.ndarray, fill: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Oracle probabilities (contact, satisfy-and-intent) for an upper-bound policy in the study."""
        o = self.cfg["outcome"]
        p = self.partners
        overload = np.maximum(0.0, fill - 0.8)
        pc = _sigmoid(
            p.contact_logit[partners]
            + o["qualified_contact"] * float(req["qualified"])
            + o["asap_contact"] * float(int(req["timeframe"]) == 0)
            + o["overload_contact"] * overload / 0.2
        )
        dist = self.dist[p.home[partners], int(req["region"])]
        ps = _sigmoid(p.skill[partners] - o["distance_penalty"] * dist + o["satisfy_bias"])
        return pc, pc * ps * self.intent_of(req)
