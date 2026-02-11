INSERT INTO dispatch_jobs (tenant_id, route_id, status, version)
VALUES ('tenant-alpha', 'north', 'drafted', 1)
ON CONFLICT DO NOTHING;
