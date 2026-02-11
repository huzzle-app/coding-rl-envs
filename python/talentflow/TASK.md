# Task: Fix the TalentFlow Application

TalentFlow is a Django-based talent management platform. The application is currently broken and all tests are failing.

## Objective

Get the application working and make **all tests pass**.

## What You Have

- A Django project in `talentflow/`
- Application code in `apps/`
- Test suite in `tests/`
- Dependencies listed in `requirements.txt`
- Docker compose file for services

## Success Criteria

```bash
pytest
```

All tests pass.

## Notes

- This project was handed off from a previous developer
- The documentation may be incomplete or outdated
- Some configuration may be missing or incorrect
- You'll need PostgreSQL and Redis running

## Debugging Scenarios

For realistic debugging practice, check out the [scenarios/](./scenarios/) directory. Each scenario simulates a production incident, support ticket, or operational alert with symptoms only - no solutions provided.

| Scenario | Type | Severity |
|----------|------|----------|
| [OAuth CSRF Attack](./scenarios/01-oauth-csrf-attack.md) | Security Incident | Critical |
| [Scheduled Tasks Wrong Time](./scenarios/02-scheduled-tasks-wrong-time.md) | Operations Incident | High |
| [Candidate Scores Missing](./scenarios/03-candidate-matching-scores-missing.md) | Support Escalation | Urgent |
| [Database Connection Timeouts](./scenarios/04-database-connection-timeouts.md) | Grafana Alert | Critical |
| [Score Calculations Wrong](./scenarios/05-candidate-score-calculations-wrong.md) | Customer Escalation | High |

These scenarios cover security, infrastructure, async tasks, database issues, and business logic bugs.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | LinkedIn import, service extraction, performance optimization, bulk API, async migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | New modules with interface contracts: Onboarding Service, Skills Assessment Engine, Referral Program |

These tasks test different software engineering skills while using the same codebase.
