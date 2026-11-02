# 4. Partner volume is reserved in Postgres

Status: accepted

## Context

Several service instances match requests at the same time. A partner who asked for 40 leads a
month must not get 41, and a retried request must not send a lead twice.

## Decision

- A lead is sent only after `UPDATE partner_capacity SET used = used + 1 WHERE partner_id = ... AND
  used < cap RETURNING ...` succeeds; the table also has `CHECK (used <= cap)`.
- If a reservation is refused, the service moves on to the next candidate.
- Decisions are keyed by request id; a retry returns the stored decision.

## Consequences

- The serving benchmark runs two instances and eight threads with every partner's volume
  squeezed to two leads, and the gate requires zero oversold leads.
- One row per partner is a hot spot for very busy partners; at Aroundhome's volume (about 4,000
  requests a day) it is far from a limit.
