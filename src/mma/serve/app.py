"""The matching service.

POST /match   a request -> up to three partners. Partner capacity lives in Postgres and is reserved
              with one conditional UPDATE, so concurrent calls (and several service processes) can
              never exceed a partner's monthly volume. A retried call returns the stored decision.
POST /events  a partner called or won; updates the feature store.
The feature store is rebuilt from the raw logs at start (the same replay the parity test checks)."""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, Field

from ..features.replay import replay, settings_for
from ..features.store import eligible
from ..matching.policies import Capacity, ModelPolicy, RuleBaseline
from ..shared.config import ROOT
from ..shared.types import BUDGETS, CATEGORIES, TIMEFRAMES, RequestObs


class MatchIn(BaseModel):
    request_id: int
    ts: float = Field(description="monitoring time in days")
    region: str
    category: str
    budget: str
    timeframe: str
    qualified: bool


class EventIn(BaseModel):
    request_id: int
    partner_id: int
    kind: str
    ts: float


class Service:
    def __init__(self, dsn: str, raw: Path, scorer=None, weights: str | None = None, days_per_month: float = 30.0):
        import pandas as pd

        self.pool = ConnectionPool(dsn, min_size=2, max_size=16, open=True)
        with self.pool.connection() as c:
            c.execute((ROOT / "migrations" / "001_serving.sql").read_text())
        self.days = days_per_month
        self.store, _, state = replay(raw, collect=False)
        self.month = state["month"]
        self.ps = pd.read_parquet(raw / "partner_settings.parquet")
        self.policy = ModelPolicy(scorer, weights) if scorer is not None else RuleBaseline()
        self.model = getattr(scorer, "version", "rules") if scorer is not None else "rules"
        self.lock = threading.Lock()
        self.latency: list[float] = []
        self.refused = 0
        self._ensure_month(self.month + 1)

    def _ensure_month(self, month: int) -> None:
        """Opens a month: partner settings into the store, caps into Postgres (idempotent)."""
        s = settings_for(self.ps, month)
        if not s:
            raise HTTPException(409, f"no partner settings for month {month}")
        self.store.update_settings(s)
        with self.pool.connection() as c:
            with c.cursor() as cur:
                cur.executemany(
                    "INSERT INTO partner_capacity (month, partner_id, cap) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    [(month, p, x.monthly_cap) for p, x in s.items()],
                )
        self.month = month

    def match(self, m: MatchIn) -> dict:
        if m.category not in CATEGORIES or m.budget not in BUDGETS or m.timeframe not in TIMEFRAMES:
            raise HTTPException(422, "unknown category, budget or timeframe")
        t0 = time.perf_counter()
        req = RequestObs(m.request_id, m.ts, m.region, m.category, m.budget, m.timeframe, m.qualified)
        month = int(m.ts // self.days)
        with self.lock:
            if month != self.month:
                self._ensure_month(month)
            with self.pool.connection() as c:
                prior = c.execute(
                    "SELECT partners, scores FROM match_decisions WHERE request_id = %s", (m.request_id,)
                ).fetchone()
                if prior:
                    return {"request_id": m.request_id, "partners": prior[0], "scores": prior[1], "replayed": True}
                cand_all = self.store.index.get((m.region, m.category), [])
                rows = c.execute(
                    "SELECT partner_id, cap, used FROM partner_capacity WHERE month = %s AND partner_id = ANY(%s)",
                    (month, cand_all),
                ).fetchall()
                cap = Capacity({r[0]: r[1] for r in rows}, {r[0]: r[2] for r in rows})
                cands = eligible(self.store, req, cap.used, cap.cap)
                chosen = self.policy.choose(req, cands, cap, self.store, month * self.days)
                scores: dict = {}
                if chosen and isinstance(self.policy, ModelPolicy):
                    pc, pw = self.policy.scorer.predict(self.store.features(req, chosen, month * self.days))
                    scores = {
                        str(p): {"p_contact": round(float(a), 4), "p_win": round(float(b), 4)}
                        for p, a, b in zip(chosen, pc, pw, strict=True)
                    }
                with c.transaction():
                    got = c.execute(
                        "UPDATE partner_capacity SET used = used + 1 WHERE month = %s AND partner_id = ANY(%s) AND used < cap RETURNING partner_id",
                        (month, chosen),
                    ).fetchall()
                    taken = [p for p in chosen if p in {g[0] for g in got}]
                    self.refused += len(chosen) - len(taken)
                    c.execute(
                        "INSERT INTO match_decisions (request_id, ts, partners, scores, model) VALUES (%s, %s, %s, %s, %s)",
                        (m.request_id, m.ts, taken, json.dumps({k: v for k, v in scores.items() if int(k) in taken}), self.model),
                    )
            for p in taken:
                self.store.record_lead(p, m.ts)
            self.store.record_request(req)
        self.latency.append((time.perf_counter() - t0) * 1000)
        return {
            "request_id": m.request_id,
            "partners": taken,
            "scores": {k: v for k, v in scores.items() if int(k) in taken},
            "replayed": False,
        }

    def event(self, e: EventIn) -> dict:
        if e.kind not in ("contacted", "won"):
            raise HTTPException(422, "kind must be contacted or won")
        with self.pool.connection() as c:
            row = c.execute(
                "SELECT ts FROM match_decisions WHERE request_id = %s AND %s = ANY(partners)", (e.request_id, e.partner_id)
            ).fetchone()
            if not row:
                raise HTTPException(404, "no such lead")
            ins = c.execute(
                "INSERT INTO lead_events VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING 1",
                (e.request_id, e.partner_id, e.kind, e.ts),
            ).fetchone()
        if ins:
            with self.lock:
                if e.kind == "contacted":
                    self.store.record_contact(e.partner_id, row[0], e.ts)
                else:
                    self.store.record_win(e.partner_id, e.ts)
        return {"recorded": bool(ins)}

    def metrics(self) -> dict:
        lat = np.array(self.latency) if self.latency else np.array([0.0])
        return {
            "matches": len(self.latency),
            "refused_by_database": self.refused,
            "p50_ms": float(np.percentile(lat, 50)),
            "p95_ms": float(np.percentile(lat, 95)),
            "model": self.model,
        }


def create_app(service_factory=None) -> FastAPI:
    holder: dict = {}

    @asynccontextmanager
    async def lifespan(app):
        if service_factory is not None:
            holder["s"] = service_factory()
        else:
            from ..models.registry import load_champion

            store = os.environ.get("MMA_MLFLOW")
            scorer = load_champion(Path(store)) if store else None
            holder["s"] = Service(
                os.environ["MMA_DATABASE_URL"], Path(os.environ["MMA_RAW"]), scorer, os.environ.get("MMA_WEIGHTS")
            )
        yield
        holder["s"].pool.close()

    app = FastAPI(title="partner matching", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"ok": True, "month": holder["s"].month}

    @app.post("/match")
    def match(m: MatchIn):
        return holder["s"].match(m)

    @app.post("/events")
    def events(e: EventIn):
        return holder["s"].event(e)

    @app.get("/metrics")
    def metrics():
        return holder["s"].metrics()

    return app
