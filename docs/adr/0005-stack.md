# 5. Stack: dbt, Airflow, MLflow, FastAPI, Postgres

Status: accepted

## Decision

- **dbt** builds the training data and its tests from raw logs (DuckDB here; the same SQL runs on
  a warehouse adapter).
- **Airflow** runs the daily pipeline: check landing, dbt build, feature parity, weekly training,
  gate and promotion, monitoring. Tasks call `python -m mma.pipeline` in the ML image, so the
  scheduler does not carry ML dependencies.
- **MLflow** holds candidates and the `champion` alias; promotion goes through a gate on
  calibration error, AUC, the drop against the current champion, and feature parity.
- **FastAPI** serves matches; **Postgres** holds capacity, decisions and lead events.
- Models are LightGBM with isotonic calibration on a later time slice.

## Consequences

- Spark is not used: a month of logs is a few hundred thousand rows. The dbt models are plain SQL
  and move to Spark SQL if the volume ever needs it.
- SageMaker or Vertex can replace the MLflow registry by swapping `mma.models.registry`; the gate
  stays the same.
