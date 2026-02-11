CREATE TABLE IF NOT EXISTS dispatch_orders (
  id TEXT PRIMARY KEY,
  severity INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
  sla_minutes INTEGER NOT NULL CHECK (sla_minutes > 0),
  status TEXT NOT NULL DEFAULT 'queued'
);

CREATE TABLE IF NOT EXISTS berth_slots (
  berth_id TEXT NOT NULL,
  start_hour INTEGER NOT NULL CHECK (start_hour >= 0 AND start_hour < 24),
  end_hour INTEGER NOT NULL CHECK (end_hour > 0 AND end_hour <= 24),
  occupied BOOLEAN NOT NULL DEFAULT FALSE,
  vessel_id TEXT,
  PRIMARY KEY (berth_id, start_hour)
);

CREATE TABLE IF NOT EXISTS vessel_manifests (
  vessel_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  cargo_tons DOUBLE PRECISION NOT NULL DEFAULT 0,
  containers INTEGER NOT NULL DEFAULT 0,
  hazmat BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS route_channels (
  channel TEXT PRIMARY KEY,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  reliability DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  priority INTEGER NOT NULL DEFAULT 0,
  blocked BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS policy_history (
  id SERIAL PRIMARY KEY,
  from_policy TEXT NOT NULL,
  to_policy TEXT NOT NULL,
  reason TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_transitions (
  id SERIAL PRIMARY KEY,
  entity_id TEXT NOT NULL,
  from_state TEXT NOT NULL,
  to_state TEXT NOT NULL,
  timestamp BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS service_registry (
  service_id TEXT PRIMARY KEY,
  port INTEGER NOT NULL,
  health_path TEXT NOT NULL DEFAULT '/health',
  version TEXT NOT NULL DEFAULT '1.0.0'
);

CREATE INDEX IF NOT EXISTS idx_dispatch_status ON dispatch_orders(status);
CREATE INDEX IF NOT EXISTS idx_berth_occupied ON berth_slots(occupied);
CREATE INDEX IF NOT EXISTS idx_workflow_entity ON workflow_transitions(entity_id);
