CREATE TABLE IF NOT EXISTS incident_tickets (
  ticket_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  severity INTEGER NOT NULL,
  subsystem TEXT NOT NULL,
  requires_manual_approval BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS replay_log (
  replay_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  events_replayed INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL
);
