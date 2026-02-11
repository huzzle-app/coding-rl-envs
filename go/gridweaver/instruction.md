# GridWeaver

 in a Go smart-grid orchestration platform with 12 services and 11 internal packages.

## Architecture

The platform uses a microservices architecture with shared internal libraries:
- **Internal packages** (`internal/`): Core business logic — topology, dispatch, estimation, security, resilience, consensus, events, concurrency, workflow, config, demand response, outage recovery
- **Services** (`services/`): 12 service modules — gateway, auth, forecast, topology, estimator, dispatch, constraint, control, outage, demandresponse, settlement, audit
- **Shared** (`shared/contracts/`): Common types for inter-service communication
- **Models** (`pkg/models/`): Domain data structures

## Known Issues

Current state: most tests broken. Main concerns include API endpoints, background processing, and database operations.

## Reward Function (8-threshold, Ultra-Principal)

| Pass Rate | Reward |
|-----------|--------|
| >= 1.00 | 1.00 |
| >= 0.95 | 0.78 |
| >= 0.85 | 0.55 |
| >= 0.70 | 0.38 |
| >= 0.55 | 0.22 |
| >= 0.40 | 0.12 |
| >= 0.25 | 0.05 |
| < 0.25 | 0.00 |

## Run

```bash
docker compose up -d
go test -race -v ./...
bash harbor/test.sh
```

## Constraints

- Do NOT modify test files (`tests/` directory)
- Do NOT modify environment files (`environment/` directory)
- Do NOT modify harbor files (`harbor/` directory)

A submission is correct when Harbor writes reward `1.0`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-region dispatch, event pipeline, topology performance, DR bidding, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Load forecasting, renewable optimizer, fault detector |

These tasks test different software engineering skills while using the same codebase.
