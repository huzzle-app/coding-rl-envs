# TalentFlow - Django Talent Management Platform

## Getting Started

```bash
# Start services
docker compose up -d

# Run tests
pytest
```

## Bug Categories

| Category | Count | Description |
|----------|-------|-------------|
| Database & ORM (A) | 3 | Connection pool, N+1 queries, race conditions |
| Celery & Async (B) | 3 | Timezone mismatch, chord callbacks, Redis leaks |
| OAuth2 & Auth (C) | 2 | JWT refresh race, CSRF vulnerability |
| Configuration (D) | 2 | Settings import order, dependency conflicts |
| Business Logic (E) | 2 | Off-by-one errors, timezone-naive comparisons |
| Heisenbugs (F) | 4 | Race conditions, data-dependent failures |
| Data-Dependent (G) | 4 | Encoding, locale, floating-point bugs |
| Cascading (H) | 3 | Deadlocks, phantom reads |
| Security (I) | 2 | SQL injection, SSRF |
| Setup Hell (S) | 6 | Circular imports, missing files, migrations |

## Key Notes

- Setup bugs (S5-S10) block startup - fix circular imports first
- Some bugs have dependencies - fixing one may require fixing another first

## Success Criteria

All tests pass when running `pytest`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | LinkedIn import, service extraction, performance optimization, bulk API, async migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | New modules with interface contracts: Onboarding Service, Skills Assessment Engine, Referral Program |

These tasks test different software engineering skills while using the same codebase.
