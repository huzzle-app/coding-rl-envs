CREATE TABLE IF NOT EXISTS missions (
  mission_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS orbital_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  fuel_kg NUMERIC NOT NULL,
  altitude_km NUMERIC NOT NULL,
  epoch TIMESTAMP NOT NULL
);
