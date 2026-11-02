"""The production pipeline, one step per Airflow task (airflow/dags/matching_pipeline.py). Works only
from raw logs in a landing directory: no truth.

    python -m mma.pipeline build     --raw DIR --warehouse FILE
    python -m mma.pipeline parity    --raw DIR --warehouse FILE --out FILE
    python -m mma.pipeline train     --warehouse FILE --cutoff DAY --store DIR --parity FILE --out FILE
    python -m mma.pipeline promote   --candidate FILE --store DIR
    python -m mma.pipeline monitor   --warehouse FILE --store DIR --cutoff DAY --out FILE
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .data.warehouse import build, training_pairs
from .features.replay import replay
from .features.store import FEATURES
from .models import registry
from .models.train import flat_metrics, train
from .monitor.drift import report
from .shared.config import load


def step_build(raw: Path, warehouse: Path) -> dict:
    return build(raw, warehouse)


def step_parity(raw: Path, warehouse: Path) -> dict:
    pairs = training_pairs(warehouse)
    _, online, _ = replay(raw)
    j = online.merge(pairs, on=["request_id", "partner_id"], suffixes=("_on", "_off"))
    mism = int(sum((~np.isclose(j[f + "_on"], j[f + "_off"], rtol=1e-9, atol=1e-9)).sum() for f in FEATURES))
    missing = int(len(pairs) - len(j))
    return {"pairs": int(len(j)), "mismatches": mism + missing}


def step_train(warehouse: Path, cutoff: float, store: Path, parity: dict) -> dict:
    scorer, metrics = train(training_pairs(warehouse), cutoff)
    flat = flat_metrics(metrics)
    version = registry.log_candidate(scorer, metrics, {"feature_mismatches": parity["mismatches"]}, store)
    champ = registry.champion(store)
    ok, why = registry.gate(flat, champ[1] if champ else None, parity["mismatches"])
    return {"version": version, "metrics": flat, "champion": champ[0] if champ else None, "passed": ok, "reasons": why}


def step_promote(candidate: dict, store: Path) -> dict:
    if not candidate["passed"]:
        return {"promoted": False, "reasons": candidate["reasons"]}
    registry.promote(candidate["version"], store)
    return {"promoted": True, "version": candidate["version"]}


def step_monitor(warehouse: Path, store: Path, cutoff: float) -> dict:
    cfg = load("monitoring")
    scorer = registry.load_champion(store)
    tr = load("models")
    train_until = cutoff - tr["contact"]["maturity_days"] - tr["contact"]["slices"]["train_end"]
    return report(training_pairs(warehouse), scorer, train_until, cfg["recent_days"], cutoff, cfg)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mma.pipeline")
    ap.add_argument("step", choices=["build", "parity", "train", "promote", "monitor"])
    ap.add_argument("--raw", type=Path)
    ap.add_argument("--warehouse", type=Path)
    ap.add_argument("--store", type=Path)
    ap.add_argument("--cutoff", type=float)
    ap.add_argument("--parity", type=Path)
    ap.add_argument("--candidate", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if a.step == "build":
        r = step_build(a.raw, a.warehouse)
    elif a.step == "parity":
        r = step_parity(a.raw, a.warehouse)
    elif a.step == "train":
        r = step_train(a.warehouse, a.cutoff, a.store, json.loads(a.parity.read_text()))
    elif a.step == "promote":
        r = step_promote(json.loads(a.candidate.read_text()), a.store)
    else:
        r = step_monitor(a.warehouse, a.store, a.cutoff)
    text = json.dumps(r, indent=1, default=float)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text)
    print(text)
    if a.step == "parity" and r["mismatches"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
