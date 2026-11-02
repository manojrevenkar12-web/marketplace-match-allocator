"""Logged history (truth side): months of matching under the current rules, written as the raw tables
the platform's logging would produce. The market (with its feature store) is returned warm, so an
evaluation month can continue from where the logs end."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..matching.policies import Capacity, RuleBaseline
from .market import Market, caps_of
from .world import World


def build_history(world: World, months: int, raw_dir: Path) -> Market:
    market = Market(world)
    policy = RuleBaseline()
    for m in range(months):
        req = world.requests(m)
        market.run(m, req, np.zeros(len(req), int), [policy], [Capacity(caps_of(world, m))], label="history")
    write_raw(world, market, months, raw_dir)
    return market


def write_raw(world: World, market: Market, months: int, raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    f = market.logs.frames()
    f["requests"].drop(columns=["label"]).to_parquet(raw_dir / "requests.parquet", index=False)
    f["matches"].drop(columns=["arm"]).to_parquet(raw_dir / "matches.parquet", index=False)
    ev = f["events"]
    if len(ev):
        # the platform only sees what has happened by the end of the logged period
        ev = ev[ev.ts < months * world.days]
    ev.to_parquet(raw_dir / "events.parquet", index=False)
    pd.concat([world.partner_table(m) for m in range(months + 1)]).to_parquet(raw_dir / "partner_settings.parquet", index=False)
