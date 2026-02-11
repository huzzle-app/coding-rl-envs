# TalentFlow - Django Debugging RL Environment

A talent management SaaS platform designed as an **extremely hard** Django debugging challenge for RL agents. Contains 25 interconnected bugs spanning PostgreSQL, Redis, Celery, OAuth2, complex ORM operations, heisenbugs, environmental issues, concurrency, and security vulnerabilities.

**Difficulty**: Senior engineer level (2-4 hours expected completion time)

## Quick Start

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# Run tests (should see ~0% pass initially)
docker-compose run --rm test

# View logs
docker-compose logs -f
```

### Using Virtual Environment

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis (required)
# You can use Docker for these:
docker run -d --name pg -e POSTGRES_PASSWORD=talentflow -e POSTGRES_USER=talentflow -e POSTGRES_DB=talentflow -p 5432:5432 postgres:15
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Run migrations
python manage.py migrate

# Run tests
pytest -v
```

## The Challenge

Your goal is to fix all 25 bugs so that all 250+ tests pass. The bugs are interconnected - some fixes may break other things, and some bugs only manifest under specific conditions. Setup bugs (S5-S10) must be fixed first before the project can even start.

### Bug Categories

| Category | Bugs | Description |
|----------|------|-------------|
| **Database & ORM** | A1, A2, A3 | Connection pool, N+1 queries, race conditions |
| **Celery & Async** | B1, B2, B3 | Timezone mismatch, chord callbacks, Redis leaks |
| **OAuth2 & Auth** | C1, C2 | JWT refresh race, CSRF vulnerability |
| **Configuration** | D1, D2 | Settings import order, dependency conflicts |
| **Business Logic** | E1, E2 | Off-by-one errors, timezone-naive comparisons |
| **Heisenbugs** | F1, F2, F3, F4 | Race conditions, data-dependent failures |
| **Data-Dependent** | G1, G2, G3, G4 | Encoding, locale, floating-point bugs |
| **Cascading** | H1, H2, H3 | Deadlocks, phantom reads |
| **Security** | I1, I2 | SQL injection, SSRF |
| **Setup Hell** | S5-S10 | Circular imports, missing files, migrations |

### Bug Details

#### A1: Connection Pool Exhaustion
- **Location**: `talentflow/settings/base.py`
- **Symptom**: Sporadic "connection refused" errors in parallel tests
- **Hint**: Check `CONN_MAX_AGE` and `CONN_HEALTH_CHECKS` settings

#### A2: N+1 Query Problem
- **Location**: `apps/candidates/views.py`
- **Symptom**: API slows linearly with data size
- **Hint**: The `prefetch_related('skills')` isn't fetching the through model

#### A3: Transaction Race Condition
- **Location**: `apps/jobs/matching.py`
- **Symptom**: Intermittent IntegrityError on concurrent applications
- **Hint**: The application limit check isn't atomic

#### B1: Timezone Mismatch
- **Location**: `talentflow/celery.py` + `settings/base.py`
- **Symptom**: Scheduled tasks run at wrong times
- **Hint**: Django and Celery have different timezone settings

#### B2: Chord Callback Broken
- **Location**: `apps/jobs/tasks.py`
- **Symptom**: Chord results are always None
- **Hint**: Check `ignore_result` setting on header tasks

#### B3: Redis Connection Leak
- **Location**: `apps/analytics/caching.py`
- **Symptom**: Connection pool exhaustion after errors
- **Hint**: Connections aren't released in error paths

#### C1: JWT Refresh Race
- **Location**: `apps/accounts/oauth.py`
- **Symptom**: Intermittent 401 on concurrent token refresh
- **Hint**: No locking during the refresh operation

#### C2: OAuth State Validation Missing
- **Location**: `apps/accounts/oauth.py`
- **Symptom**: CSRF vulnerability in OAuth flow
- **Hint**: State parameter is passed but not validated

#### D1: Settings Import Order
- **Location**: `talentflow/settings/__init__.py`
- **Symptom**: DEBUG=True in production
- **Hint**: Development settings imported before environment check

#### D2: psycopg2 Conflict
- **Location**: `requirements.txt`
- **Symptom**: ImportError on Linux
- **Hint**: Both psycopg2 and psycopg2-binary are listed

#### E1: Skill Matching Off-by-One
- **Location**: `apps/jobs/matching.py`
- **Symptom**: Perfect skill matches score 0.99 instead of 1.0
- **Hint**: Division uses wrong denominator

#### E2: Timezone-Naive Datetime
- **Location**: `apps/interviews/scheduling.py`
- **Symptom**: Wrong availability calculations around DST
- **Hint**: Naive datetimes compared with aware datetimes

## Test Suite

The test suite contains 250+ tests across 4 categories:

| Category | Weight | Location |
|----------|--------|----------|
| Unit | 1.0x | `tests/unit/` |
| Integration | 1.5x | `tests/integration/` |
| System | 2.5x | `tests/system/` |
| Security | 2.0x | `tests/security/` |

### Running Specific Tests

```bash
# Run all tests
pytest

# Run by category
pytest tests/unit/
pytest tests/integration/
pytest tests/system/
pytest tests/security/

# Run tests for specific bug
pytest -m bug_a1
pytest -m bug_c2

# Run with verbose output
pytest -v --tb=long
```

## Reward Function

The reward is calculated as:

```
Reward = (0.40 × test_pass_score) +
         (0.25 × completion_bonus) +
         (0.25 × bug_bonus) +
         (0.05 × efficiency_bonus) -
         (0.15 × regression_penalty)
```

| Component | Weight | Description |
|-----------|--------|-------------|
| Test Pass Score | 40% | Sparse thresholds at 25%/50%/75%/90%/100% pass rate, weighted by category |
| Completion Bonus | 25% | All-or-nothing per category; requires 2+ categories fully complete |
| Bug Bonus | 25% | Fractional credit per bug with dependency penalties |
| Efficiency Bonus | 5% | pass_rate × remaining step budget |
| Regression Penalty | 15% | Penalty for tests that were passing but now fail |

## RL Environment API

```python
from environment import TalentFlowEnvironment

# Initialize
env = TalentFlowEnvironment(max_steps=100)

# Reset to initial buggy state
observation = env.reset()

# Take actions and observe results
while True:
    action = {
        'type': 'edit',
        'file': 'apps/candidates/views.py',
        'content': '...'
    }
    result = env.step(action)

    print(f"Reward: {result.reward}")
    print(f"Tests passed: {result.observation['test_results']['passed']}")

    if result.done:
        print("Challenge completed!")
        break
    if result.truncated:
        print("Max steps reached")
        break
```

## Project Structure

```
talentflow/
├── talentflow/           # Django project
│   ├── settings/         # Settings with bugs D1
│   ├── celery.py        # Celery config with bug B1
│   └── urls.py
├── apps/
│   ├── accounts/        # OAuth bugs C1, C2
│   ├── candidates/      # N+1 bug A2
│   ├── jobs/           # Race condition A3, matching bug E1, chord bug B2
│   ├── interviews/     # Timezone bug E2
│   └── analytics/      # Redis leak B3
├── tests/              # 250+ test cases
├── environment/        # RL environment wrapper
├── docker-compose.yml
└── requirements.txt    # With bug D2
```

## Success Criteria

- All 250+ pytest tests pass
- Reward = 1.0

Good luck!
