CREATE TABLE IF NOT EXISTS dispatch_orders (
  id TEXT PRIMARY KEY,
  urgency INTEGER NOT NULL CHECK (urgency BETWEEN 1 AND 5),
  sla_minutes INTEGER NOT NULL CHECK (sla_minutes > 0),
  severity INTEGER NOT NULL DEFAULT 3,
  status TEXT NOT NULL DEFAULT 'queued',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vessel_manifests (
  vessel_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  cargo_tons DOUBLE PRECISION NOT NULL DEFAULT 0,
  containers INTEGER NOT NULL DEFAULT 0,
  hazmat BOOLEAN NOT NULL DEFAULT FALSE,
  registered_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS routes (
  channel TEXT PRIMARY KEY,
  latency INTEGER NOT NULL DEFAULT 0,
  reliability DOUBLE PRECISION NOT NULL DEFAULT 1.0,
  distance_nm DOUBLE PRECISION NOT NULL DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS berth_slots (
  id SERIAL PRIMARY KEY,
  berth_id TEXT NOT NULL,
  start_hour INTEGER NOT NULL,
  end_hour INTEGER NOT NULL,
  occupied BOOLEAN NOT NULL DEFAULT FALSE,
  vessel_id TEXT REFERENCES vessel_manifests(vessel_id),
  CONSTRAINT valid_hours CHECK (end_hour > start_hour)
);

CREATE TABLE IF NOT EXISTS policy_history (
  id SERIAL PRIMARY KEY,
  from_policy TEXT NOT NULL,
  to_policy TEXT NOT NULL,
  reason TEXT,
  changed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_transitions (
  id SERIAL PRIMARY KEY,
  entity_id TEXT NOT NULL,
  from_state TEXT NOT NULL,
  to_state TEXT NOT NULL,
  timestamp BIGINT NOT NULL,
  recorded_at TIMESTAMP NOT NULL DEFAULT NOW()
);

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

CREATE INDEX IF NOT EXISTS idx_dispatch_orders_status ON dispatch_orders(status);
CREATE INDEX IF NOT EXISTS idx_dispatch_orders_urgency ON dispatch_orders(urgency DESC);
CREATE INDEX IF NOT EXISTS idx_berth_slots_berth ON berth_slots(berth_id);
CREATE INDEX IF NOT EXISTS idx_workflow_entity ON workflow_transitions(entity_id);
CREATE INDEX IF NOT EXISTS idx_replay_events_seq ON replay_events(sequence);
CREATE INDEX IF NOT EXISTS idx_token_store_issued ON token_store(issued_at);
