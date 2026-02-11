INSERT INTO shipments (shipment_id, lane, units, priority, created_at)
VALUES
  ('s-100', 'north', 12, 3, NOW()),
  ('s-200', 'south', 8, 2, NOW())
ON CONFLICT (shipment_id) DO NOTHING;
