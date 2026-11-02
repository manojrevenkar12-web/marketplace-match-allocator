"""Serving benchmark (truth side, because it generates traffic from the simulated world): two service
instances share one Postgres and race for the same partners from many threads; afterwards no partner
may have more leads than its monthly volume. Also measures per-call latency with the trained model."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import psycopg

from ..models.train import load_local
from ..serve.app import MatchIn, Service
from ..shared.config import ROOT
from ..sim.market import obs
from ..sim.world import World


def reset(dsn: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute("DROP TABLE IF EXISTS partner_capacity, match_decisions, lead_events")


def bench(
    dsn: str, raw: Path, scorer_path: Path | None, world: World, n: int = 3000, threads: int = 8, squeeze: int | None = 2
) -> dict:
    reset(dsn)
    scorer = load_local(scorer_path) if scorer_path else None
    a = Service(dsn, raw, scorer)
    b = Service(dsn, raw, scorer)
    month = a.month
    if squeeze is not None:
        with psycopg.connect(dsn, autocommit=True) as c:
            c.execute("UPDATE partner_capacity SET cap = least(cap, %s) WHERE month = %s", (squeeze, month))
    req = world.requests(month, stream=7)
    req = req.iloc[:n]
    ins = [MatchIn(**{**obs(world, r).__dict__}) for r in req.itertuples(index=False)]

    def call(i: int):
        return (a if i % 2 else b).match(ins[i])

    with ThreadPoolExecutor(threads) as ex:
        res = list(ex.map(call, range(len(ins))))
    with psycopg.connect(dsn) as c:
        over = c.execute("SELECT count(*) FROM partner_capacity WHERE used > cap").fetchone()[0]
        per = dict(
            c.execute("SELECT partner_id, count(*) FROM match_decisions, unnest(partners) AS p(partner_id) GROUP BY 1").fetchall()
        )
        caps = dict(c.execute("SELECT partner_id, cap FROM partner_capacity WHERE month = %s", (month,)).fetchall())
        used = dict(c.execute("SELECT partner_id, used FROM partner_capacity WHERE month = %s", (month,)).fetchall())
    oversold = sum(max(0, k - caps.get(p, 0)) for p, k in per.items())
    mismatched = sum(1 for p, k in per.items() if used.get(p) != k)
    replay = a.match(ins[0])
    lat = np.array(a.latency + b.latency)
    return {
        "requests": len(ins),
        "service_instances": 2,
        "threads": threads,
        "cap_squeezed_to": squeeze,
        "leads": int(sum(per.values())),
        "oversold_leads": int(oversold),
        "reservations_refused_by_database": int(a.refused + b.refused),
        "decisions_vs_counter_mismatches": int(mismatched),
        "counters_over_cap": int(over),
        "retry_returns_same_decision": bool(replay["replayed"] and replay["partners"] == res[0]["partners"]),
        "p50_ms": float(np.percentile(lat, 50)),
        "p95_ms": float(np.percentile(lat, 95)),
        "model": a.model,
    }


def run(profile: str, dsn: str) -> dict:
    from .study import make_world
    from .study import profile as prof

    out = ROOT / "runs" / profile
    world = make_world(prof(profile))
    r = {
        "contention": bench(dsn, out / "raw", out / "scorer.pkl", world, squeeze=2),
        "latency": bench(dsn, out / "raw", out / "scorer.pkl", world, n=2000, threads=1, squeeze=None),
    }
    (out / "serving.json").write_text(json.dumps(r, indent=1))
    return r
