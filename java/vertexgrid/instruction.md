Fix production defects in VertexGrid by editing source code only.

VertexGrid is an Apex-Principal Java 21 environment with 1250 bugs and 15,000+ test scenarios spanning Spring lifecycle, distributed state, JPA correctness, security controls, and observability boundaries.

## Architecture

Maven multi-module reactor with 11 microservice modules:

| Module | Description | Tests |
|--------|-------------|-------|
| shared | Core utilities: EventBus, CollectionUtils, Config, Security, Observability | ~12,100 |
| gateway | HTTP gateway: request routing, security filters, file handling | ~18 |
| auth | Authentication: JWT tokens, validation, session management | ~15 |
| vehicles | Vehicle management: CRUD, model validation | ~37 |
| routes | Route planning: cost calculation, BigDecimal operations | ~530 |
| dispatch | Dispatch optimization: scheduling, concurrent listeners | ~36 |
| tracking | Real-time tracking: GPS, speed, position aggregation | ~550 |
| billing | Invoice processing: pricing, discounts, route billing | ~580 |
| analytics | Analytics pipeline: CSV, pagination, caching, metrics | ~560 |
| notifications | Notification delivery: email, push, caching | ~21 |
| compliance | Regulatory compliance: FMCSA hours-of-service, break rules | ~590 |

## Bug Categories

| Category | ID Range | Description |
|----------|----------|-------------|
| Collection/Data Structure | C1-C10 | EnumSet.of varargs, HashMap identity, toMap duplicates |
| Event/Messaging | E1-E5 | Polymorphic dispatch, event ordering, throughput |
| Lifecycle/Config | L1-L8 | Kafka config, Spring wiring, circular deps |
| Security | S1-S6 | JWT validation, SQL injection, path traversal, SSRF |
| Financial/Precision | F1-F10 | BigDecimal rounding, double precision, integer division |
| Data Processing | G1-G4 | Return type overflow, divide-by-zero, pagination |
| Behavioral | B1-B5 | Duplicate key handling, sort direction, null guards |
| Pattern Matching | K1-K5 | Unsafe casts, type erasure |
| Observability | O1-O5 | Log level case sensitivity, metric collection |

## Getting Started

```bash
# Build all modules (compile only)
mvn install -DskipTests -B -q

# Run full test suite
mvn test -B -fn

# Run a single module
mvn test -pl billing -B
```

## Constraints

- Do not modify files under `src/test/`.
- Preserve deterministic replay and scheduling behavior.
- Keep security checks, policy gates, and audit invariants intact.

Primary objective: make the full suite pass (`mvn test -B`) with production-safe changes for an Apex-Principal environment.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Geofencing alerts, monetary refactoring, pipeline optimization, REST API v2, dispatch migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Energy Consumption Analyzer, Demand Response Coordinator, Carbon Footprint Calculator |

These tasks test different software engineering skills while using the same codebase.
