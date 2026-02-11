CREATE TABLE IF NOT EXISTS incidents (
  incident_id TEXT PRIMARY KEY,
  severity INTEGER NOT NULL,
  domain TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS replay_log (
  replay_id TEXT PRIMARY KEY,
  shipment_id TEXT NOT NULL,
  events_replayed INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL
);
