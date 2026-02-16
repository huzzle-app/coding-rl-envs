Fix production defects in NebulaChain by editing source code only.

NebulaChain is an Apex-Principal JavaScript environment with issues and tests focused on dispatch governance, replay safety, and policy/routing hardening.

## Architecture

NebulaChain uses a three-layer architecture:

1. **Core modules** (`src/core/`): scheduling, routing, resilience, policy, queue, security, statistics, workflow
2. **Service layer** (`services/`): gateway, audit, analytics, notifications, policy, resilience, routing, security
3. **Shared contracts** (`shared/contracts/`): service definitions, topology, inter-service communication

All bugs are embedded in the source codes in source files. Bugs span:

- 9 core modules (~54 bugs): off-by-one errors, wrong sort orders, missing validations, incorrect constants
- 8 service modules (~40 bugs): logic inversions, missing checks, wrong weights, encoding bypasses
- Shared contracts (~5 bugs): protocol errors, missing fields, incomplete cycle detection

## Getting Started

```bash
npm test
```

## Test Breakdown

| Category | Count |
|----------|-------|
| Unit tests | 9 |
| Integration tests | 3 |
| Service contract test | 1 |
| Service tests (8 x 4) | 32 |
| Stress: hyper-matrix | 7,000 |
| Stress: service-mesh-matrix | 2,168 |
| Stress: state-machine-matrix | 620 |
| Stress: integration-domain-matrix | 480 |
| Stress: concurrency-matrix | 540 |
| Stress: latent-multistep-matrix | 360 |
| Stress: async-pipeline-matrix | 360 |
| Stress: cross-module-pipeline-matrix | 320 |
| **Total** | **11,893** |

## Reward Tiers (10-threshold Apex)

| Pass Rate | Reward |
|-----------|--------|
| >= 1.0 | 1.0 |
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

- Do not modify files under `tests/`.
- Preserve deterministic replay and scheduling behavior.
- Keep security checks, policy gates, and audit invariants intact.

Primary objective: make the full suite pass (`npm test`) — all 11,893 tests green — with production-safe changes for an Apex-Principal environment.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Consensus Quorum Validation, Replay Strategy Pattern, Route Table Indexing, Distributed Transaction Coordinator, Event Sourcing Schema |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Smart Contract Validator, Block Explorer Backend, Token Transfer Service |

These tasks test different software engineering skills while using the same codebase.
