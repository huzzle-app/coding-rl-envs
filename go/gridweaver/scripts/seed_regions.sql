INSERT INTO dispatch_plans (id, region, generation_mw, reserve_mw, curtailment_mw)
VALUES ('seed-1', 'west', 1000, 150, 0)
ON CONFLICT (id) DO NOTHING;
