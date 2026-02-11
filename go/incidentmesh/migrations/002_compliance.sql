CREATE TABLE IF NOT EXISTS compliance_audit (
  id TEXT PRIMARY KEY,
  incident_id TEXT NOT NULL,
  override_reason TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
