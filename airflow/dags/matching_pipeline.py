"""Daily matching pipeline: land raw logs -> dbt build (models + tests) -> training/serving parity ->
weekly candidate training with MLflow -> gate -> promote -> monitoring.

Each task runs `python -m mma.pipeline <step>` in the ML image, so the scheduler's environment stays
free of ML dependencies (MMA_PYTHON points at that interpreter; MMA_DATA at the data root)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import ShortCircuitOperator
from airflow.sdk import DAG

PY = os.environ.get("MMA_PYTHON", "python3")
DATA = os.environ.get("MMA_DATA", "/opt/mma/data")
CUTOFF = os.environ.get(
    "MMA_CUTOFF_DAY", "{{ (data_interval_end - macros.datetime(2026, 1, 1, tzinfo=data_interval_end.tzinfo)).days }}"
)
RAW, WH, STORE, OUT = f"{DATA}/raw", f"{DATA}/warehouse.duckdb", f"{DATA}/mlflow", f"{DATA}/pipeline"


def _training_day(**context) -> bool:
    """Train on Mondays, or whenever MMA_TRAIN_ALWAYS is set (backfills, tests)."""
    return bool(os.environ.get("MMA_TRAIN_ALWAYS")) or context["data_interval_end"].weekday() == 0


with DAG(
    dag_id="partner_matching",
    schedule="0 5 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=10)},
    tags=["matching", "ml"],
) as dag:
    land = BashOperator(
        task_id="check_landing",
        bash_command=f"test -s {RAW}/requests.parquet && test -s {RAW}/matches.parquet && test -s {RAW}/events.parquet",
    )
    build = BashOperator(
        task_id="dbt_build", bash_command=f"{PY} -m mma.pipeline build --raw {RAW} --warehouse {WH} --out {OUT}/dbt.json"
    )
    parity = BashOperator(
        task_id="feature_parity", bash_command=f"{PY} -m mma.pipeline parity --raw {RAW} --warehouse {WH} --out {OUT}/parity.json"
    )
    monday = ShortCircuitOperator(task_id="is_training_day", python_callable=_training_day, ignore_downstream_trigger_rules=False)
    train = BashOperator(
        task_id="train_candidate",
        bash_command=f"{PY} -m mma.pipeline train --warehouse {WH} --cutoff {CUTOFF} --store {STORE} --parity {OUT}/parity.json --out {OUT}/candidate.json",
    )
    promote = BashOperator(
        task_id="gate_and_promote",
        bash_command=f"{PY} -m mma.pipeline promote --candidate {OUT}/candidate.json --store {STORE} --out {OUT}/promotion.json",
    )
    monitor = BashOperator(
        task_id="monitor",
        bash_command=f"{PY} -m mma.pipeline monitor --warehouse {WH} --store {STORE} --cutoff {CUTOFF} --out {OUT}/monitoring.json",
        trigger_rule="none_failed",
    )
    land >> build >> parity >> monday >> train >> promote >> monitor
