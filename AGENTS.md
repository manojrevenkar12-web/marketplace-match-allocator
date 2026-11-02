# Working on this repository

## Fast feedback

- `pytest -q -m "not slow and not db"`: seconds.
- `pytest -q`: adds the pipeline tests (builds a small world) and the serving tests (needs
  Postgres in `MMA_TEST_DATABASE_URL`).
- `mma all --profile quick`: study, held-out rerun, serving benchmark (if `MMA_DATABASE_URL` is
  set), report and release gate in a few minutes. This is what CI runs.
- `scripts/airflow_dag_test.sh`: the Airflow DAG end to end on sample logs.
- `cd web && npm test && npx playwright test`: the dashboard.
- `ruff check` and `ruff format --check` (Python), `npx biome ci src e2e` (web) before a commit.

## Invariants (each has a test or a gate check)

- **Truth isolation.** Only `mma.sim`, `mma.evaluate` and `scripts/sample_data.py` import the
  simulator. Features, models, matching, pipeline, serving and monitoring work from logged data only
  (`tests/test_isolation.py`).
- **One definition of each feature.** The online store and dbt must agree on every logged lead;
  any mismatch fails the pipeline (ADR 3).
- **No partner gets more leads than they asked for.** Reservations happen in Postgres (ADR 4);
  the gate requires zero oversold leads.
- **Settings live in `config/`**, not in code: weights, pacing, windows, gate thresholds,
  experiment designs.
- **Generated files are not edited by hand:** `docs/REPORT.md`, `reports/results.json`,
  `reports/heldout/*/first_run.json`.

## Held-out markets

`heldout/<set>/scenarios` were written from `heldout/WRITING_SCENARIOS.md` by someone who never
saw the code. Never change matching, features or models to do better on a held-out set. The first
full run of a set is recorded in `reports/heldout/<set>/first_run.json` and is never rewritten. If
you study a set's failures, write `regression` to `heldout/<set>/STATUS` and have someone who has
not seen the code write a new set from the brief only.
