INSERT INTO compliance_audit (id, incident_id, override_reason)
VALUES ('seed-1', 'inc-1', 'initial override reason')
ON CONFLICT (id) DO NOTHING;
