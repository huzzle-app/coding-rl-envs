# GeneForge - Distributed Clinical Genomics Analysis Platform

You are debugging a Rust platform for distributed clinical genomics workflows:
sequence ingestion, alignment orchestration, variant calling pipelines,
cohort aggregation, phenotype correlation, and compliance-safe reporting.

The codebase contains issues across 13 services. All tests must pass before completion.

## Services

- Gateway
- Auth
- Sample Intake
- QC Pipeline
- Aligner
- Variant Caller
- Annotation Engine
- Cohort Aggregator
- Phenotype Matcher
- Report Generator
- Consent Guard
- Billing
- Audit

## Infrastructure

- NATS
- PostgreSQL
- Redis
- Object Storage
- etcd

## Bug ID Taxonomy

| ID Range | Category |
|----------|----------|
| GEN001-GEN012 | Setup/Config |
| GEN013-GEN034 | Async/Concurrency |
| GEN035-GEN050 | Memory/Ownership |
| GEN051-GEN068 | Pipeline Ordering |
| GEN069-GEN084 | Data Integrity |
| GEN085-GEN098 | Numerical/Statistical |
| GEN099-GEN112 | Security/Privacy |
| GEN113-GEN124 | Resilience |
| GEN125-GEN136 | Observability |

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents:

| Scenario | Type | Description |
| [01-qc-batch-rejections.md](./scenarios/01-qc-batch-rejections.md) | PagerDuty Alert | QC pipeline rejecting valid samples at boundary thresholds |
| [02-consent-compliance-audit.md](./scenarios/02-consent-compliance-audit.md) | Compliance Audit | HIPAA/GDPR violations in consent management |
| [03-statistical-analysis-errors.md](./scenarios/03-statistical-analysis-errors.md) | Customer Escalation | Statistical calculation errors affecting research publications |
| [04-pipeline-failures.md](./scenarios/04-pipeline-failures.md) | Slack Discussion | Retry storms and stage transition failures |
| [05-resilience-circuit-breaker.md](./scenarios/05-resilience-circuit-breaker.md) | P0 Incident | Cascading failures from circuit breaker malfunction |

These scenarios describe **symptoms only** and are designed to train realistic debugging skills.

## Success Criteria

- All 1200+ tests pass.
- Privacy/security suites are fully green.
- Final full-suite pass rate reaches 100%.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Confidence scoring, pipeline modularization, QC throughput, federated consent, state machine |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Variant caller service, alignment validator, population frequency calculator |

These tasks test different software engineering skills while using the same codebase.
