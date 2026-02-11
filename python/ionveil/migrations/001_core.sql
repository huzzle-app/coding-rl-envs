-- IonVeil Core Schema Migration

-- Organizations
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'dispatcher',
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_users_org_id ON users(org_id);
CREATE INDEX idx_users_email ON users(email);

-- Incidents
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    severity INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
    priority INTEGER NOT NULL DEFAULT 3,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    incident_type VARCHAR(100),
    location_lat DOUBLE PRECISION,
    location_lng DOUBLE PRECISION,
    estimated_cost DOUBLE PRECISION DEFAULT 0.0,
    actual_cost DOUBLE PRECISION DEFAULT 0.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    last_audit_id UUID REFERENCES audit_events(id),
    version INTEGER DEFAULT 1  -- for optimistic locking
);

CREATE INDEX idx_incidents_org_id ON incidents(org_id);
-- CREATE INDEX idx_incidents_status ON incidents(status);
CREATE INDEX idx_incidents_created_at ON incidents(created_at);
CREATE INDEX idx_incidents_severity ON incidents(severity);

-- Units (fire trucks, ambulances, police cars, etc.)
CREATE TABLE IF NOT EXISTS units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    unit_type VARCHAR(50) NOT NULL,  -- fire, medical, police, hazmat
    status VARCHAR(50) NOT NULL DEFAULT 'available',
    location_lat DOUBLE PRECISION,
    location_lng DOUBLE PRECISION,
    certifications TEXT[] DEFAULT '{}',
    shift_start TIME,
    shift_end TIME,
    max_capacity INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_units_org_id ON units(org_id);
CREATE INDEX idx_units_status ON units(status);
CREATE INDEX idx_units_type ON units(unit_type);

-- Assignments (links incidents to units)
CREATE TABLE IF NOT EXISTS assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    unit_id UUID NOT NULL REFERENCES units(id),
    assigned_at TIMESTAMPTZ DEFAULT now(),
    eta_minutes INTEGER,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    notes TEXT,
    -- audit-relevant assignment records. Should use ON DELETE SET NULL or RESTRICT.
    UNIQUE(incident_id, unit_id)
);

CREATE INDEX idx_assignments_incident ON assignments(incident_id);
CREATE INDEX idx_assignments_unit ON assignments(unit_id);

-- Routes
CREATE TABLE IF NOT EXISTS routes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    origin_lat DOUBLE PRECISION NOT NULL,
    origin_lng DOUBLE PRECISION NOT NULL,
    dest_lat DOUBLE PRECISION NOT NULL,
    dest_lng DOUBLE PRECISION NOT NULL,
    distance_km DOUBLE PRECISION,
    duration_minutes INTEGER,
    segments JSONB DEFAULT '[]',
    is_blocked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Audit Events (should be BEFORE incidents for the FK to work)
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    actor_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_audit_org_id ON audit_events(org_id);
CREATE INDEX idx_audit_created ON audit_events(created_at);

-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    token_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    is_active BOOLEAN DEFAULT true
);

-- API Keys
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    key_value VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT now(),
    is_active BOOLEAN DEFAULT true
);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID REFERENCES incidents(id),
    channel VARCHAR(50) NOT NULL,  -- email, sms, push, radio
    recipient VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- SLA Configurations
CREATE TABLE IF NOT EXISTS sla_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    severity INTEGER NOT NULL,
    response_minutes INTEGER NOT NULL,
    resolution_minutes INTEGER NOT NULL,
    UNIQUE(org_id, severity)
);

-- Metrics (for analytics)
CREATE TABLE IF NOT EXISTS response_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID REFERENCES incidents(id),
    metric_name VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    labels JSONB DEFAULT '{}',
    recorded_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_metrics_incident ON response_metrics(incident_id);
CREATE INDEX idx_metrics_name ON response_metrics(metric_name);
