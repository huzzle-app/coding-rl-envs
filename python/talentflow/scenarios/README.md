# TalentFlow Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, and operational alerts you might encounter as an engineer on the TalentFlow team.

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable behavior, error messages, and user reports. Your task is to:

1. Reproduce the issue (if possible)
2. Investigate root cause
3. Identify the buggy code
4. Implement a fix
5. Verify the fix doesn't cause regressions

## Scenario Index

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-oauth-csrf-attack.md](./01-oauth-csrf-attack.md) | Security Incident | Critical | OAuth state parameter not validated, CSRF vulnerability |
| [02-scheduled-tasks-wrong-time.md](./02-scheduled-tasks-wrong-time.md) | Operations Incident | High | Background tasks running 5 hours late, timezone mismatch |
| [03-candidate-matching-scores-missing.md](./03-candidate-matching-scores-missing.md) | Support Escalation | Urgent | Batch scoring returns null scores despite task success |
| [04-database-connection-timeouts.md](./04-database-connection-timeouts.md) | Grafana Alert | Critical | Connection pool exhausted, request timeouts |
| [05-candidate-score-calculations-wrong.md](./05-candidate-score-calculations-wrong.md) | Customer Escalation | High | Match scores consistently lower than expected |

## Difficulty Progression

These scenarios cover different areas of the application:

- **Scenario 1**: Security - OAuth flow and CSRF protection
- **Scenario 2**: Infrastructure - Celery/Django configuration mismatch
- **Scenario 3**: Async Tasks - Celery chord pattern issues
- **Scenario 4**: Database - Connection pooling and race conditions
- **Scenario 5**: Business Logic - Algorithm and calculation bugs

## Tips for Investigation

1. **Run tests first**: `pytest` will reveal which tests are currently failing
2. **Check logs for patterns**: Error messages often point to specific code paths
3. **Search for related code**: `grep -rn "keyword" apps/`
4. **Review recent changes**: `git log --oneline -20` to see recent commits
5. **Use Django shell**: `python manage.py shell` to test code interactively

## Related Documentation

- [TASK.md](../TASK.md) - Full environment description
- Test files in `tests/` directory contain assertions that exercise these bugs

## Environment Setup

Before investigating, ensure you have the environment running:

```bash
# Start services
docker compose up -d

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Run tests to see current state
pytest
```
