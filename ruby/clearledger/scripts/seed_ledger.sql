INSERT INTO settlement_batches (tenant_id, status)
VALUES ('tenant-alpha', 'drafted')
ON CONFLICT DO NOTHING;
