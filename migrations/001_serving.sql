-- Serving state. Postgres is the record of capacity and of every match decision.
CREATE TABLE IF NOT EXISTS partner_capacity (
  month      int NOT NULL,
  partner_id int NOT NULL,
  cap        int NOT NULL CHECK (cap >= 0),
  used       int NOT NULL DEFAULT 0,
  PRIMARY KEY (month, partner_id),
  CONSTRAINT used_within_cap CHECK (used <= cap)
);
-- One decision per request: a retried call gets the same answer.
CREATE TABLE IF NOT EXISTS match_decisions (
  request_id bigint PRIMARY KEY,
  ts         double precision NOT NULL,
  partners   int[] NOT NULL,
  scores     jsonb NOT NULL,
  model      text NOT NULL,
  decided_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS lead_events (
  request_id bigint NOT NULL,
  partner_id int NOT NULL,
  kind       text NOT NULL CHECK (kind IN ('contacted', 'won')),
  ts         double precision NOT NULL,
  PRIMARY KEY (request_id, partner_id, kind)
);
