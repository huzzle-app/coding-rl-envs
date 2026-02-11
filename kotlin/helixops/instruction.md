Fix production defects in HelixOps by editing source code only.

HelixOps is an Apex-Principal Kotlin environment and **12,tests** covering coroutine safety, Exposed ORM correctness, Ktor pipeline integrity, serialization fidelity, security hardening, and observability paths.

## Architecture

| Layer | Path | Description |
|-------|------|-------------|
| Shared | `shared/` | Config loading, security providers, event bus, serialization, delegation, caching, models, observability |
| Gateway | `gateway/` | Ktor request pipeline, auth gates, routing fanout |
| Auth | `auth/` | JWT validation, key rotation, access control |
| Documents | `documents/` | Document lifecycle and repository integrity |
| Search | `search/` | Query planning, scoring, cache coordination |
| Graph | `graph/` | Graph traversal and topology consistency |
| Embeddings | `embeddings/` | Vector generation and storage resilience |
| Collab | `collab/` | WebSocket and async collaboration state |
| Billing | `billing/` | Ledger rounding and invoice correctness |
| Notifications | `notifications/` | Alert dispatch and retry safety |
| Analytics | `analytics/` | Metrics aggregation and observability flow |

| Category | Core IDs | Count |
|----------|----------|-------|
| Setup/Config | L1-L5 | 5 |
| Coroutines | A1-A10 | 10 |
| Null Safety | B1-B6 | 6 |
| Data Classes/Sealed | C1-C8 | 8 |
| Ktor Pipeline | D1-D5 | 5 |
| Exposed ORM | E1-E8 | 8 |
| Serialization | F1-F7 | 7 |
| Delegation | G1-G5 | 5 |
| Caching | H1-H5 | 5 |
| Security | I1-I8 | 8 |
| Observability | J1-J5 | 5 |
| Modern Kotlin | K1-K8 | 8 |

## Getting Started

```bash
docker compose up -d
./gradlew test --continue --no-daemon
```

## Test Breakdown

| Category | Count |
|----------|-------|
| Shared unit tests (10 test classes) | ~200 |
| Service tests (10 modules) | ~400 |
| Hyper matrix (stress, @TestFactory) | 12,000 |
| **Total** | **12,600+** |

## Reward Tiers (10-threshold, Apex)

| Pass Rate | Reward |
|-----------|--------|
| >= 1.00 | 1.0 |
| >= 0.99 | 0.85 |
| >= 0.96 | 0.66 |
| >= 0.90 | 0.47 |
| >= 0.80 | 0.31 |
| >= 0.67 | 0.19 |
| >= 0.52 | 0.11 |
| >= 0.36 | 0.05 |
| >= 0.22 | 0.015 |
| < 0.22 | 0.0 |

## Constraints

- Do not modify test files under `src/test/`.
- Preserve deterministic replay and scheduling behavior.
- Keep security checks, policy gates, and audit invariants intact.
- All changes must be production-safe.

Primary objective: make the full suite pass (`./gradlew test`) with production-safe changes.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | API key management, unified query DSL, connection pooling, GraphQL federation, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | SSO integration, document templates, usage analytics |

These tasks test different software engineering skills while using the same codebase.
