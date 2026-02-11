Fix production defects in AtlasDispatch by editing source code only.

Constraints:
- Do not modify files under `tests/`.
- Preserve deterministic replay and routing behavior.
- Keep security and policy controls enforced.

Primary objective: make the full suite pass with robust production-safe fixes.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-carrier routing, queue refactoring, replay optimization, scheduling API, policy migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Proof of Delivery, Dynamic Rerouting, Driver Performance Tracker |

These tasks test different software engineering skills while using the same codebase.
