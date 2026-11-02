"""Write raw logs for a small simulated market (for the Airflow DAG test and local tries).

This is the only place outside mma.evaluate that touches the simulator: it plays the part of the
production systems that land logs in the data lake."""

from __future__ import annotations

import argparse
from pathlib import Path

from mma.sim.history import build_history
from mma.sim.world import World, world_config


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--requests", type=int, default=6000)
    ap.add_argument("--partners", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    w = World(world_config({"requests_per_month": a.requests, "partners": a.partners}), a.seed)
    build_history(w, w.cfg["history_months"], a.out)
    print(f"raw logs for {w.cfg['history_months']} months in {a.out}")


if __name__ == "__main__":
    main()
