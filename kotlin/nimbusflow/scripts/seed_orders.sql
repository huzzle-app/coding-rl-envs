INSERT INTO dispatch_orders (id, urgency, sla_minutes, severity, status) VALUES
  ('K-100', 4, 45, 4, 'queued'),
  ('K-101', 5, 15, 5, 'queued'),
  ('K-102', 3, 60, 3, 'allocated'),
  ('K-103', 2, 120, 2, 'departed'),
  ('K-104', 1, 240, 1, 'arrived'),
  ('K-105', 4, 30, 4, 'queued'),
  ('K-106', 5, 20, 5, 'allocated'),
  ('K-107', 3, 90, 3, 'queued');

INSERT INTO vessel_manifests (vessel_id, name, cargo_tons, containers, hazmat) VALUES
  ('V-001', 'MV Nimbus Star', 45000.0, 900, FALSE),
  ('V-002', 'MV Storm Carrier', 72000.0, 1500, TRUE),
  ('V-003', 'MV Breeze Swift', 18000.0, 360, FALSE),
  ('V-004', 'MV Cumulus Gate', 55000.0, 1100, FALSE);

INSERT INTO routes (channel, latency, reliability, distance_nm, active) VALUES
  ('north-atlantic', 12, 0.95, 3200.0, TRUE),
  ('south-pacific', 18, 0.88, 4800.0, TRUE),
  ('med-transit', 8, 0.97, 1200.0, TRUE),
  ('arctic-bypass', 24, 0.72, 5600.0, FALSE);

INSERT INTO berth_slots (berth_id, start_hour, end_hour, occupied, vessel_id) VALUES
  ('B-01', 6, 14, TRUE, 'V-001'),
  ('B-01', 14, 22, FALSE, NULL),
  ('B-02', 8, 20, TRUE, 'V-002'),
  ('B-03', 0, 12, FALSE, NULL);
