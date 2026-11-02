"""The warehouse: dbt (DuckDB) builds staging, point-in-time features and marts from raw logs."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import duckdb
import pandas as pd

from ..shared.config import ROOT

DBT_DIR = ROOT / "dbt"


def dbt(command: str, raw_dir: Path, warehouse: Path, *extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "MMA_WAREHOUSE": str(warehouse), "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
    args = [
        "dbt",
        command,
        "--project-dir",
        str(DBT_DIR),
        "--profiles-dir",
        str(DBT_DIR),
        "--vars",
        json.dumps({"raw": str(raw_dir)}),
        *extra,
    ]
    return subprocess.run(args, cwd=DBT_DIR, env=env, capture_output=True, text=True)


def build(raw_dir: Path, warehouse: Path) -> dict:
    """dbt build: models and their tests. Raises with dbt's output if anything fails."""
    r = dbt("build", raw_dir, warehouse)
    if r.returncode != 0:
        raise RuntimeError(f"dbt build failed:\n{r.stdout[-4000:]}\n{r.stderr[-2000:]}")
    results = json.loads((DBT_DIR / "target" / "run_results.json").read_text())
    statuses = [x["status"] for x in results["results"]]
    return {
        "nodes": len(statuses),
        "tests": sum(1 for x in results["results"] if x["unique_id"].startswith("test.")),
        "failed": sum(s in ("fail", "error") for s in statuses),
    }


def training_pairs(warehouse: Path) -> pd.DataFrame:
    with duckdb.connect(str(warehouse), read_only=True) as con:
        return con.execute("select * from fct_training_pairs order by ts, request_id, partner_id").df()
