#!/usr/bin/env bash
# Run the partner_matching DAG once, end to end, against a small simulated data lake.
# Needs: Airflow 3.1 and this package installed in the same interpreter.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
work="${1:-$(mktemp -d)}"
export AIRFLOW_HOME="$work/airflow"
export AIRFLOW__CORE__DAGS_FOLDER="$here/airflow/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export MMA_PYTHON="${MMA_PYTHON:-python3}"
export MMA_DATA="$work/data"
export MMA_CUTOFF_DAY=120
export MMA_TRAIN_ALWAYS=1
export MLFLOW_DISABLE_AGENT_HINT=1
"$MMA_PYTHON" "$here/scripts/sample_data.py" "$MMA_DATA/raw"
airflow db migrate >/dev/null
airflow dags reserialize >/dev/null
airflow dags test partner_matching 2026-05-04 2>&1 | tee "$work/dag-test.log" | grep -E "DagRun Finished|ERROR" || true
grep -q "DagRun Finished.*state=success" "$work/dag-test.log"
"$MMA_PYTHON" - "$MMA_DATA/pipeline" <<'PY'
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
dbt, parity, promo = (json.loads((d / f).read_text()) for f in ("dbt.json", "parity.json", "promotion.json"))
mon = json.loads((d / "monitoring.json").read_text())
print(f"dbt {dbt}; parity mismatches {parity['mismatches']}; promotion {promo}; monitoring keys {sorted(mon)[:6]}")
assert dbt["failed"] == 0 and parity["mismatches"] == 0
PY
