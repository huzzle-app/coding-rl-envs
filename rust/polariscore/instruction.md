# PolarisCore - Hyper-Principal Logistics Orchestration Environment

## Overview
- **Name:** PolarisCore
- **Language:** Rust
- **Bug Count:** ~32 bugs across 9 source modules
- **Test Count:** 164 test functions (133 in hyper_matrix + 31 in targeted test files)
- **Difficulty:** Hyper-Principal (70-140h expected)

## Bug Categories
| Category | Count | Files |
|----------|-------|-------|
| Statistics | 5 | statistics.rs |
| Workflow | 5 | workflow.rs |
| Resilience | 4 | resilience.rs |
| Queue | 4 | queue.rs |
| Allocator | 3 | allocator.rs |
| Routing | 3 | routing.rs |
| Economics | 3 | economics.rs |
| Security | 2 | security.rs |
| Policy | 3 | policy.rs |

## Getting Started
```bash
docker compose up -d
cargo test
```

## Constraints
- Do not edit files under `tests/`.
- Preserve deterministic ordering behavior in routing/queue/allocator code.
- Maintain security and policy invariants.

## Success Criteria
- Full test suite passes (`cargo test`) with all scenarios.
- All bugs fixed in source files only.
- No regressions in existing functionality.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-zone scheduling, risk refactoring, queue optimization, tracking API, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Weather Impact Assessor, Cold Chain Monitor, Expedition Cost Estimator |

These tasks test different software engineering skills while using the same codebase.
