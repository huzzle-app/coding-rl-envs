-- IonVeil Resilience & Event Sourcing Schema

-- Event store for event sourcing
CREATE TABLE IF NOT EXISTS event_store (
    id BIGSERIAL PRIMARY KEY,
    stream_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    -- Events can appear out of order if clock skews
    sequence TIMESTAMPTZ DEFAULT now(),
    partition_key VARCHAR(100),
    correlation_id UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_events_stream ON event_store(stream_id);
CREATE INDEX idx_events_type ON event_store(event_type);
CREATE INDEX idx_events_sequence ON event_store(sequence);

-- Replay checkpoints
CREATE TABLE IF NOT EXISTS replay_checkpoints (
    checkpoint_id VARCHAR(255) PRIMARY KEY,
    stream_id UUID NOT NULL,
    last_sequence BIGINT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Distributed locks
CREATE TABLE IF NOT EXISTS distributed_locks (
    lock_key VARCHAR(255) PRIMARY KEY,
    holder_id UUID NOT NULL,
    acquired_at TIMESTAMPTZ DEFAULT now(),
    -- If holder crashes, lock is held forever
    metadata JSONB DEFAULT '{}'
);

-- Saga state
CREATE TABLE IF NOT EXISTS saga_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    saga_type VARCHAR(100) NOT NULL,
    current_step INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'running',
    steps_completed JSONB DEFAULT '[]',
    compensation_data JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Leader election
CREATE TABLE IF NOT EXISTS leader_registry (
    service_name VARCHAR(255) PRIMARY KEY,
    leader_id UUID NOT NULL,
    elected_at TIMESTAMPTZ DEFAULT now(),
    last_heartbeat TIMESTAMPTZ DEFAULT now(),
    term INTEGER DEFAULT 1
);

-- Service discovery
CREATE TABLE IF NOT EXISTS service_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(255) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL,
    health_status VARCHAR(50) DEFAULT 'healthy',
    metadata JSONB DEFAULT '{}',
    registered_at TIMESTAMPTZ DEFAULT now(),
    last_heartbeat TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_service_name ON service_registry(service_name);

-- Feature flags
CREATE TABLE IF NOT EXISTS feature_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_name VARCHAR(255) UNIQUE NOT NULL,
    is_enabled BOOLEAN DEFAULT false,
    rollout_percentage INTEGER DEFAULT 0,
    conditions JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Cache metadata (for distributed cache coordination)
CREATE TABLE IF NOT EXISTS cache_metadata (
    cache_key VARCHAR(500) PRIMARY KEY,
    shard_id INTEGER NOT NULL,
    ttl_seconds INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ
);

-- Preserve metadata as JSONB to keep indexing and json operators available.
-- If a previous revision stored text payloads, cast them back to JSONB safely.
ALTER TABLE incidents
    ALTER COLUMN metadata TYPE JSONB
    USING COALESCE(NULLIF(metadata::text, '')::jsonb, '{}'::jsonb);
ALTER TABLE incidents
    ALTER COLUMN metadata SET DEFAULT '{}'::jsonb;

-- Compliance reports
CREATE TABLE IF NOT EXISTS compliance_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    report_type VARCHAR(100) NOT NULL,
    time_range_start TIMESTAMPTZ NOT NULL,
    time_range_end TIMESTAMPTZ NOT NULL,
    data JSONB NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT now()
);
