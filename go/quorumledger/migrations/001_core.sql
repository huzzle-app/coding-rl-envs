CREATE TABLE IF NOT EXISTS ledger_entries (
  entry_id TEXT PRIMARY KEY,
  account TEXT NOT NULL,
  amount_cents BIGINT NOT NULL,
  currency TEXT NOT NULL,
  sequence BIGINT NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS quorum_votes (
  vote_id TEXT PRIMARY KEY,
  node_id TEXT NOT NULL,
  epoch BIGINT NOT NULL,
  approved BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL
);
