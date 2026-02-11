CREATE TABLE IF NOT EXISTS dispatch_orders (
  id TEXT PRIMARY KEY,
  severity INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
  sla_minutes INTEGER NOT NULL CHECK (sla_minutes >= 0),
  status TEXT NOT NULL DEFAULT 'queued',
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS berth_slots (
  berth_id TEXT NOT NULL,
  start_hour INTEGER NOT NULL,
  end_hour INTEGER NOT NULL CHECK (end_hour > start_hour),
  occupied BOOLEAN NOT NULL DEFAULT FALSE,
  vessel_id TEXT,
  PRIMARY KEY (berth_id, start_hour)
);

CREATE TABLE IF NOT EXISTS vessel_manifests (
  vessel_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  cargo_tons DOUBLE PRECISION NOT NULL DEFAULT 0,
  containers INTEGER NOT NULL DEFAULT 0,
  hazmat BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS route_channels (
  channel TEXT PRIMARY KEY,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  reliability DOUBLE PRECISION NOT NULL DEFAULT 1.0,
  priority INTEGER NOT NULL DEFAULT 5,
  blocked BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS policy_history (
  id SERIAL PRIMARY KEY,
  from_state TEXT NOT NULL,
  to_state TEXT NOT NULL,
  reason TEXT,
  changed_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflow_transitions (
  id SERIAL PRIMARY KEY,
  entity_id TEXT NOT NULL,
  from_state TEXT NOT NULL,
  to_state TEXT NOT NULL,
  transitioned_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS replay_events (
  event_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  payload JSONB,
  received_at TIMESTAMP NOT NULL DEFAULT now(),
  PRIMARY KEY (event_id, sequence)
);

CREATE TABLE IF NOT EXISTS service_registry (
  service_id TEXT PRIMARY KEY,
  port INTEGER NOT NULL,
  health_path TEXT NOT NULL DEFAULT '/health',
  version TEXT NOT NULL DEFAULT '1.0.0',
  last_heartbeat TIMESTAMP
);

CREATE INDEX idx_dispatch_status ON dispatch_orders(status);
CREATE INDEX idx_workflow_entity ON workflow_transitions(entity_id);
CREATE INDEX idx_replay_sequence ON replay_events(sequence);
