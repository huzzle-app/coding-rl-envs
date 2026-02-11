INSERT INTO genomic_samples (id, cohort, stage)
VALUES ('seed-1', 'cohort-a', 'qc')
ON CONFLICT (id) DO NOTHING;
