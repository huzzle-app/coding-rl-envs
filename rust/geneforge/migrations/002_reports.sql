CREATE TABLE IF NOT EXISTS clinical_reports (
  id TEXT PRIMARY KEY,
  sample_id TEXT NOT NULL,
  findings INT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
