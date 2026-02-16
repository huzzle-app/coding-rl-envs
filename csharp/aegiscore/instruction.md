Fix production defects in AegisCore by editing source code only.

## Environment

AegisCore is a hyper-principal maritime dispatch reliability platform built with C# 12 / .NET 8. It coordinates vessel berth allocation, multi-leg route planning, policy escalation, circuit breaker resilience, and real-time workflow tracking across eight interconnected services.

## Codebase Structure

- `src/AegisCore/Domain.cs` - Core domain types: DispatchOrder, Route, ReplayEvent, VesselManifest, Severity, OrderFactory
- `src/AegisCore/Allocator.cs` - Berth allocation, dispatch planning, cost estimation, rolling window scheduler
- `src/AegisCore/Routing.cs` - Route selection, channel scoring, multi-leg planning, transit time estimation
- `src/AegisCore/Policy.cs` - Policy state machine with escalation/de-escalation, SLA compliance checks
- `src/AegisCore/QueueGuard.cs` - Load shedding, priority queue, token-bucket rate limiting, health monitoring
- `src/AegisCore/Security.cs` - SHA-256 digest, HMAC manifest signing, token store, path sanitization
- `src/AegisCore/Resilience.cs` - Event replay/deduplication, circuit breaker FSM, checkpoint management
- `src/AegisCore/Statistics.cs` - Descriptive stats, percentile, response time tracking, heatmap generation
- `src/AegisCore/Workflow.cs` - State machine transitions, BFS shortest path, entity lifecycle with audit log
- `src/AegisCore/Contracts.cs` - Service registry, topological ordering, URL resolution, dependency validation

## Constraints

- Do not modify files under `tests/`.
- Preserve deterministic replay and routing behavior.
- Keep security and policy controls enforced.
- All thread-safe classes use `lock` for synchronization - maintain this pattern.

## Bug Count

30+ issues across 10 modules with cross-module dependency chains.

## Running Tests

```bash
cd csharp/aegiscore && dotnet test
```

Primary objective: make the full suite pass with robust production-safe fixes.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | RBAC integration, Queue refactoring, Circuit breaker perf, Security events, Token store migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Threat Detection Engine, Access Log Analyzer, Secret Rotation Service |

These tasks test different software engineering skills while using the same codebase.
