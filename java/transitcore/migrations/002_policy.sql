CREATE TABLE IF NOT EXISTS policy_decisions (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
