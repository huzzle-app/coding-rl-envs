CREATE TABLE IF NOT EXISTS shipments (
  shipment_id TEXT PRIMARY KEY,
  lane TEXT NOT NULL,
  units INTEGER NOT NULL,
  priority INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS windows (
  window_id TEXT PRIMARY KEY,
  start_minute INTEGER NOT NULL,
  end_minute INTEGER NOT NULL,
  capacity INTEGER NOT NULL
);
