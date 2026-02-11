CREATE TABLE IF NOT EXISTS replay_events (
  id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  payload TEXT,
  received_at TIMESTAMP NOT NULL DEFAULT NOW(),
  PRIMARY KEY (id, sequence)
);

CREATE TABLE IF NOT EXISTS checkpoints (
  id TEXT PRIMARY KEY,
  sequence BIGINT NOT NULL,
  timestamp BIGINT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS circuit_breaker_state (
  service_id TEXT PRIMARY KEY,
  state TEXT NOT NULL DEFAULT 'closed',
  failure_count INTEGER NOT NULL DEFAULT 0,
  success_count INTEGER NOT NULL DEFAULT 0,
  last_transition TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS token_store (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL,
  issued_at BIGINT NOT NULL,
  ttl_seconds BIGINT NOT NULL,
  revoked BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_replay_events_seq ON replay_events(sequence);
CREATE INDEX IF NOT EXISTS idx_token_store_issued ON token_store(issued_at);
