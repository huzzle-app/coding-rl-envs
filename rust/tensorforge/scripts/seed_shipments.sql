INSERT INTO dispatch_orders (id, severity, sla_minutes, status) VALUES
  ('V-100', 4, 45, 'queued'),
  ('V-101', 5, 15, 'queued'),
  ('V-102', 3, 60, 'allocated'),
  ('V-103', 2, 120, 'queued'),
  ('V-104', 5, 10, 'departed'),
  ('V-105', 4, 30, 'queued'),
  ('V-106', 1, 240, 'arrived'),
  ('V-107', 3, 90, 'queued'),
  ('V-108', 4, 25, 'allocated'),
  ('V-109', 5, 15, 'queued');

INSERT INTO berth_slots (berth_id, start_hour, end_hour, occupied, vessel_id) VALUES
  ('B-01', 0, 6, true, 'V-201'),
  ('B-01', 6, 12, false, NULL),
  ('B-01', 12, 18, true, 'V-202'),
  ('B-01', 18, 24, false, NULL),
  ('B-02', 0, 8, false, NULL),
  ('B-02', 8, 16, true, 'V-203'),
  ('B-02', 16, 24, false, NULL),
  ('B-03', 0, 12, false, NULL),
  ('B-03', 12, 24, true, 'V-204');

INSERT INTO vessel_manifests (vessel_id, name, cargo_tons, containers, hazmat) VALUES
  ('V-201', 'MV Atlantic Dawn', 45000.0, 3200, false),
  ('V-202', 'MV Pacific Herald', 62000.0, 4800, true),
  ('V-203', 'MV Northern Star', 38000.0, 2600, false),
  ('V-204', 'MV Southern Cross', 55000.0, 4100, true);

INSERT INTO route_channels (channel, latency_ms, reliability, priority, blocked) VALUES
  ('alpha', 5, 0.95, 8, false),
  ('beta', 3, 0.98, 7, false),
  ('gamma', 8, 0.85, 5, false),
  ('delta', 12, 0.70, 3, true),
  ('epsilon', 2, 0.99, 9, false);

INSERT INTO service_registry (service_id, port, health_path, version) VALUES
  ('gateway', 8120, '/health', '1.0.0'),
  ('routing', 8121, '/health', '1.0.0'),
  ('policy', 8122, '/health', '1.0.0'),
  ('resilience', 8123, '/health', '1.0.0'),
  ('analytics', 8124, '/health', '1.0.0'),
  ('audit', 8125, '/health', '1.0.0'),
  ('notifications', 8126, '/health', '1.0.0'),
  ('security', 8127, '/health', '1.0.0');
