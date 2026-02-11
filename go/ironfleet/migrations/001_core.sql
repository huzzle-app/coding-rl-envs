CREATE TABLE IF NOT EXISTS dispatch_orders (
  id TEXT PRIMARY KEY,
  severity INTEGER NOT NULL,
  sla_minutes INTEGER NOT NULL
);
