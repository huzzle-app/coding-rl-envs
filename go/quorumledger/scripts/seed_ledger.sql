INSERT INTO ledger_entries (entry_id, account, amount_cents, currency, sequence, created_at)
VALUES
  ('e1', 'acct-a', 100000, 'USD', 1, NOW()),
  ('e2', 'acct-b', -50000, 'USD', 1, NOW()),
  ('e3', 'acct-c', 50000, 'USD', 1, NOW())
ON CONFLICT (entry_id) DO NOTHING;
