INSERT INTO missions (mission_id, status, created_at)
VALUES
  ('mission-alpha', 'active', NOW()),
  ('mission-bravo', 'active', NOW()),
  ('mission-charlie', 'degraded', NOW())
ON CONFLICT (mission_id) DO NOTHING;
