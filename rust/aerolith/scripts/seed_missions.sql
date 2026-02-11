INSERT INTO mission_commands (id, region, command_type)
VALUES ('seed-1', 'leo-eu', 'burn.plan')
ON CONFLICT (id) DO NOTHING;
