# 3. One definition of each feature, two implementations checked against each other

Status: accepted

## Context

The model is trained on features computed in the warehouse from logs and scored on features
computed online at request time. If the two differ, offline metrics say nothing about production.

## Decision

- Every feature is a count or sum over event timestamps in a window ending at the request time.
  The windows are in `config/features.yaml` and passed to dbt as vars.
- dbt computes them with point-in-time (ASOF) joins on running counts; the online feature store
  keeps sorted timestamps and counts with binary search.
- The pipeline replays the logs through the online store and compares every feature of every
  logged lead with the warehouse. Any mismatch fails the run and blocks training.
- Labels are used only once they have matured (three days for a call, forty for a won project).

## Consequences

- New features have to be expressible as windowed counts or sums, or come with their own parity
  check.
- The parity step costs about a minute per month of logs.
