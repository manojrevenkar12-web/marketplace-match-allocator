"""The study (truth side): logged history -> dbt -> features -> calibrated models, then the evaluation
month replayed under each policy and each experiment design, against the true global effect."""

from __future__ import annotations

import copy
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.warehouse import build as dbt_build
from ..data.warehouse import training_pairs
from ..experiments.designs import assign, estimate
from ..features.replay import replay
from ..features.store import FEATURES
from ..matching.policies import Capacity, ModelPolicy, RuleBaseline
from ..models.train import load_local, save_local, train
from ..shared.config import load, run_dir
from ..sim.history import build_history
from ..sim.market import Market, caps_of
from ..sim.world import World, world_config

METRICS = ["project", "revenue", "partner_profit", "contacted"]


def profile(name: str) -> dict:
    return load("profiles")[name]


def make_world(p: dict, override: dict | None = None) -> World:
    cfg = world_config(p.get("world"))
    if override:
        from ..shared.config import deep_merge

        cfg = deep_merge(cfg, override)
    return World(cfg, p["seed"])


def summarize(df: pd.DataFrame) -> dict:
    leads = max(1, int(df.leads.sum()))
    return {
        "requests": int(len(df)),
        "matched": float((df.n_matched > 0).mean()),
        "leads": leads,
        "leads_per_request": float(df.n_matched.mean()),
        "contacted": float(df.contacted.mean()),
        "project": float(df.project.mean()),
        "revenue": float(df.revenue.mean()),
        "partner_profit": float(df.partner_profit.mean()),
        "partner_profit_per_lead": float(df.partner_profit.sum() / leads),
        "wins_per_lead": float(df.wins.sum() / leads),
    }


def prepare(name: str, world: World, out: Path, log=print) -> tuple[Market, dict]:
    """History, warehouse, parity check and models."""
    months = world.cfg["history_months"]
    t0 = time.time()
    market = build_history(world, months, out / "raw")
    log(f"history: {months} months in {time.time() - t0:.0f} s")
    t0 = time.time()
    dbt = dbt_build(out / "raw", out / "warehouse.duckdb")
    log(f"dbt build: {dbt} in {time.time() - t0:.0f} s")
    pairs = training_pairs(out / "warehouse.duckdb")
    _, online, _ = replay(out / "raw")
    j = online.merge(pairs, on=["request_id", "partner_id"], suffixes=("_on", "_off"))
    mism = {f: int((~np.isclose(j[f + "_on"], j[f + "_off"], rtol=1e-9, atol=1e-9)).sum()) for f in FEATURES}
    parity = {
        "pairs": int(len(j)),
        "online_rows": int(len(online)),
        "offline_rows": int(len(pairs)),
        "mismatches": int(sum(mism.values())),
        "by_feature": mism,
    }
    log(f"feature parity: {parity['mismatches']} mismatches over {parity['pairs']} pairs")
    scorer, metrics = train(pairs, months * world.days)
    save_local(scorer, out / "scorer.pkl")
    log(
        f"models: contact AUC {metrics['contact']['test']['auc']:.3f} ECE {metrics['contact']['test']['ece']:.4f}; win AUC {metrics['win']['test']['auc']:.3f} ECE {metrics['win']['test']['ece']:.4f}"
    )
    return market, {"dbt": dbt, "parity": parity, "models": metrics, "training_rows": int(len(pairs))}


def _global(base: Market, world: World, month: int, req: pd.DataFrame, policy) -> pd.DataFrame:
    m = copy.deepcopy(base)
    m.keep_logs = False
    return m.run(month, req, np.zeros(len(req), int), [policy], [Capacity(caps_of(world, month))])


def replication(args) -> dict:
    """One evaluation month: true effect from global runs, then every design."""
    base, world, scorer_path, k, designs = args
    scorer = load_local(scorer_path)
    month = world.cfg["history_months"]
    req = world.requests(month, stream=k)
    caps = caps_of(world, month)
    out: dict = {"stream": k}
    g_rules = _global(base, world, month, req, RuleBaseline())
    g_model = _global(base, world, month, req, ModelPolicy(scorer))
    out["truth"] = {m: float(g_model[m].mean() - g_rules[m].mean()) for m in METRICS}
    out["global"] = {"rules": summarize(g_rules), "model": summarize(g_model)}
    out["designs"] = {}
    for d in designs:
        a = assign(d, req, caps, salt=1000 + k)
        m = copy.deepcopy(base)
        m.keep_logs = False
        df = m.run(month, req, a.arms, [RuleBaseline(), ModelPolicy(scorer)], a.views)
        out["designs"][d] = {mt: estimate(df, a.arms, a.clusters, mt) for mt in METRICS}
    # A/A on the budget split: the same rules in both arms; any "effect" is the design's own error
    a = assign("budget_split", req, caps, salt=5000 + k)
    m = copy.deepcopy(base)
    m.keep_logs = False
    df = m.run(month, req, a.arms, [RuleBaseline(), RuleBaseline()], a.views)
    out["aa_budget_split"] = {mt: estimate(df, a.arms, a.clusters, mt) for mt in METRICS}
    return out


def frontier(base: Market, world: World, scorer_path: Path) -> dict:
    scorer = load_local(scorer_path)
    month = world.cfg["history_months"]
    req = world.requests(month, stream=0)
    out = {"rules": summarize(_global(base, world, month, req, RuleBaseline()))}
    for w in load("matching")["weights"]:
        out[w] = summarize(_global(base, world, month, req, ModelPolicy(scorer, w, name=w)))
    out["balanced_without_pacing"] = summarize(_global(base, world, month, req, ModelPolicy(scorer, pacing=False)))
    return out


def aggregate(reps: list[dict], designs: list[str], alpha: float) -> dict:
    out = {}
    for d in designs:
        out[d] = {}
        for mt in METRICS:
            est = np.array([r["designs"][d][mt]["estimate"] for r in reps])
            tru = np.array([r["truth"][mt] for r in reps])
            cover = np.array([r["designs"][d][mt]["lo"] <= r["truth"][mt] <= r["designs"][d][mt]["hi"] for r in reps])
            se = np.array([r["designs"][d][mt]["se"] for r in reps])
            out[d][mt] = {
                "mean_estimate": float(est.mean()),
                "mean_truth": float(tru.mean()),
                "bias": float((est - tru).mean()),
                "relative_bias": float((est - tru).mean() / tru.mean()) if abs(tru.mean()) > 1e-12 else None,
                "rmse": float(np.sqrt(((est - tru) ** 2).mean())),
                "coverage": float(cover.mean()),
                "mean_se": float(se.mean()),
                "replications": len(reps),
            }
    return out


def run_study(name: str, log=print) -> dict:
    p = profile(name)
    out = run_dir(name)
    world = make_world(p)
    base, prep = prepare(name, world, out, log)
    designs = list(load("experiments")["designs"])
    t0 = time.time()
    args = [(base, world, out / "scorer.pkl", k, designs) for k in range(p["replications"])]
    with ProcessPoolExecutor(max_workers=p["workers"]) as ex:
        reps = list(ex.map(replication, args))
    log(f"{len(reps)} replications in {time.time() - t0:.0f} s")
    front = frontier(base, world, out / "scorer.pkl")
    aa = {
        mt: float(np.mean([not (r["aa_budget_split"][mt]["lo"] <= 0 <= r["aa_budget_split"][mt]["hi"]) for r in reps]))
        for mt in METRICS
    }
    result = {
        "profile": name,
        "prepare": prep,
        "designs": {d: load("experiments")["designs"][d]["about"] for d in designs},
        "experiments": aggregate(reps, designs, load("experiments")["alpha"]),
        "aa_budget_split_false_positive_rate": aa,
        "replications": reps,
        "frontier": front,
        "world": {
            "requests_per_month": world.cfg["requests_per_month"],
            "partners": world.cfg["partners"],
            "regions": world.R,
            "categories": world.C,
        },
    }
    (out / "study.json").write_text(json.dumps(result, indent=1))
    return result
