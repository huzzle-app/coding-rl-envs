CREATE TABLE IF NOT EXISTS grid_commands (
  id TEXT PRIMARY KEY,
  region TEXT NOT NULL,
  command_type TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS grid_events (
  id TEXT PRIMARY KEY,
  region TEXT NOT NULL,
  event_type TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
