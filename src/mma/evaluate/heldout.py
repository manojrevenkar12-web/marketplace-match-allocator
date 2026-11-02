"""Blind held-out worlds: written from heldout/WRITING_SCENARIOS.md by someone who never saw the code.
Each world goes through the whole pipeline (history, dbt, parity, training) and is evaluated on its
fifth month: the model policy against the rules globally, and two experiment designs against that
truth. A set's first full run is recorded once and never rewritten."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import yaml

from ..experiments.designs import assign, estimate
from ..matching.policies import ModelPolicy, RuleBaseline
from ..models.train import load_local
from ..shared.config import ROOT, deep_merge, load, run_dir
from ..sim.market import caps_of
from ..sim.world import World, world_config
from .study import METRICS, _global, prepare, summarize


def scenarios(set_name: str) -> tuple[list[dict], str]:
    d = ROOT / "heldout" / set_name / "scenarios"
    files = sorted(d.glob("*.yaml"))
    h = hashlib.sha256()
    out = []
    for f in files:
        text = f.read_text()
        h.update(f.name.encode() + text.encode())
        out.append(yaml.safe_load(text))
    return out, h.hexdigest()


def status(set_name: str) -> str:
    p = ROOT / "heldout" / set_name / "STATUS"
    return p.read_text().strip() if p.exists() else "heldout"


def first_run_path(set_name: str) -> Path:
    return ROOT / "reports" / "heldout" / set_name / "first_run.json"


def evaluate_world(world: World, out: Path, log=print) -> dict:
    base, prep = prepare("heldout", world, out, log)
    scorer = load_local(out / "scorer.pkl")
    month = world.cfg["history_months"]
    req = world.requests(month, stream=0)
    caps = caps_of(world, month)
    g_rules = _global(base, world, month, req, RuleBaseline())
    g_model = _global(base, world, month, req, ModelPolicy(scorer))
    truth = {m: float(g_model[m].mean() - g_rules[m].mean()) for m in METRICS}
    designs = {}
    for d in ("request_split", "budget_split"):
        a = assign(d, req, caps, salt=77)
        m = copy.deepcopy(base)
        m.keep_logs = False
        df = m.run(month, req, a.arms, [RuleBaseline(), ModelPolicy(scorer)], a.views)
        designs[d] = {mt: estimate(df, a.arms, a.clusters, mt) for mt in METRICS}
    return {
        "rules": summarize(g_rules),
        "model": summarize(g_model),
        "truth": truth,
        "designs": designs,
        "parity_mismatches": prep["parity"]["mismatches"],
        "models": {k: prep["models"][k]["test"] for k in ("contact", "win")},
    }


def run_heldout(profile: str, set_name: str | None = None, log=print) -> dict:
    set_name = set_name or load("profiles").get("heldout_set", "v1")
    scs, sha = scenarios(set_name)
    p = load("profiles")[profile]
    out = run_dir(profile) / "heldout"
    results = []
    for sc in scs:
        cfg = deep_merge(world_config(), sc.get("overrides") or {})
        if profile != "full":
            # a smaller world for CI: the same shape at a quarter of the volume
            cfg["requests_per_month"] = max(2000, int(cfg["requests_per_month"] * p.get("heldout_scale", 0.25)))
            cfg["partners"] = max(100, int(cfg["partners"] * p.get("heldout_scale", 0.25)))
        world = World(cfg, int(sc["seed"]))
        log(f"held-out {sc['name']}: {cfg['requests_per_month']} requests, {cfg['partners']} partners")
        r = evaluate_world(world, out / sc["name"], log)
        results.append({"name": sc["name"], "about": sc.get("about", ""), **r})
    lifts = [r["model"]["project"] - r["rules"]["project"] for r in results]
    rev = [r["model"]["revenue"] / r["rules"]["revenue"] for r in results]
    summary_ = {
        "scenarios": len(results),
        "project_lift_share": float(np.mean([x > 0 for x in lifts])),
        "mean_project_lift": float(np.mean(lifts)),
        "min_revenue_ratio": float(min(rev)),
        "mean_revenue_ratio": float(np.mean(rev)),
        "budget_split_project_covered": float(
            np.mean(
                [
                    r["designs"]["budget_split"]["project"]["lo"]
                    <= r["truth"]["project"]
                    <= r["designs"]["budget_split"]["project"]["hi"]
                    for r in results
                ]
            )
        ),
        "request_split_project_covered": float(
            np.mean(
                [
                    r["designs"]["request_split"]["project"]["lo"]
                    <= r["truth"]["project"]
                    <= r["designs"]["request_split"]["project"]["hi"]
                    for r in results
                ]
            )
        ),
    }
    res = {
        "set": set_name,
        "status": status(set_name),
        "profile": profile,
        "sha256": sha,
        "summary": summary_,
        "results": results,
    }
    (run_dir(profile) / "heldout.json").write_text(json.dumps(res, indent=1))
    fp = first_run_path(set_name)
    if profile == "full" and status(set_name) == "heldout" and not fp.exists():
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(json.dumps({**res, "recorded_at": datetime.now(UTC).isoformat()}, indent=1))
        log(f"recorded the first run of {set_name}")
    return res
