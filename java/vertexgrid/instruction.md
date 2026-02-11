Fix production defects in VertexGrid by editing source code only.

VertexGrid is an Apex-principal Java environment with issues and 12,000+ stress scenarios spanning Spring lifecycle, distributed state, JPA correctness, security controls, and observability boundaries.

Constraints:
- Do not modify files under `tests/`.
- Preserve deterministic replay and scheduling behavior.
- Keep security checks, policy gates, and audit invariants intact.

Primary objective: make the full suite pass (`mvn -q test`) with production-safe changes for an Apex-Principal environment.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Geofencing alerts, monetary refactoring, pipeline optimization, REST API v2, dispatch migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Energy Consumption Analyzer, Demand Response Coordinator, Carbon Footprint Calculator |

These tasks test different software engineering skills while using the same codebase.
