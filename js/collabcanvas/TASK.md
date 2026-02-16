# CollabCanvas - Real-time Collaborative Whiteboard Debug Challenge

## Objective

You are debugging a real-time collaborative whiteboard application built with Node.js, Express, Socket.io, PostgreSQL, and Redis. The application has **25 intentional bugs** that cause tests to fail. Your goal is to identify and fix all bugs to achieve **100% test pass rate** .

**Difficulty Level**: Senior Engineer (2-4 hours expected)

## Getting Started

```bash
# Install dependencies
npm install

# Start services with Docker
docker compose up -d

# Run tests (will fail initially)
npm test

# Or with Docker
docker compose --profile test up --build
```

## Architecture

```
collabcanvas/
├── src/
│ ├── config/ # Configuration (bugs F2, F4)
│ ├── models/ # Sequelize models
│ ├── services/
│ │ ├── canvas/ # CRDT, sync, history (bugs A1, A2, B1-B4)
│ │ ├── collaboration/ # Presence, broadcast (bugs A3, A4)
│ │ ├── board/ # Board management (bugs C1, C2)
│ │ ├── storage/ # File uploads (bugs E1-E4)
│ │ └── auth/ # JWT, OAuth (bugs D1-D4)
│ ├── websocket/ # Socket.io handlers (bug A5)
│ ├── routes/ # REST API endpoints
│ └── middleware/ # Auth, error handling
├── tests/
│ ├── unit/ # Unit tests
│ ├── integration/ # Integration tests
│ ├── system/ # System tests
│ └── security/ # Security tests
└── environment/ # RL environment wrapper
```

## Infrastructure

- **PostgreSQL 15** - User data, boards, elements
- **Redis 7** - Caching, pub/sub for real-time sync

## Known Issues

Test failures indicate issues in core modules. Some infrastructure code may also need review.

## Key Challenges

1. **JavaScript-Specific Bugs**: Many bugs exploit JavaScript's quirks:
 - Type coercion (`'10' > '9'` is false in string comparison)
 - Missing `await` on async operations
 - `this` binding issues with arrow functions
 - Closure capturing stale references
 - Prototype pollution vulnerabilities

2. **Real-time Sync Bugs**: WebSocket handlers have race conditions and memory leaks that only manifest with multiple concurrent users.

3. **Cascading Failures**: Some bugs depend on others:
 - A2 (race condition) requires A1 (await) fixed
 - B4 (history) requires B2 (deep copy) fixed
 - D4 (socket auth) requires D1 (JWT secret) fixed

## Test Categories

| Category | Tests | Weight |
| Unit | 141 | 1.0x |
| Integration | 38 | 1.5x |
| System | 36 | 2.5x |
| Security | 44 | 2.0x |

## Hints

### Setup Bugs (Fix These First!)

1. **F2**: Check `src/config/index.js` - circular import with `database.js`
2. **F4**: Check `src/config/database.js` - `process.env.DB_POOL_SIZE` is string
3. **F1**: Check `package.json` - socket.io version mismatch

### Common Bug Patterns

- **Missing await**: Functions return before async operations complete
- **Shallow copy**: Using `{...obj}` loses nested properties
- **Type coercion**: `process.env` values are always strings
- **Stale closures**: Event handlers capture variables by reference
- **No hasOwnProperty**: Prototype pollution in object iteration

### Key Files to Examine

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents you might encounter:

| Scenario | Type | Description |
| [01-realtime-sync-failures.md](scenarios/01-realtime-sync-failures.md) | PagerDuty Incident | Lost edits and sync failures during collaboration |
| [02-security-audit-findings.md](scenarios/02-security-audit-findings.md) | Security Report | Penetration test findings for file uploads and OAuth |
| [03-memory-leak-presence.md](scenarios/03-memory-leak-presence.md) | Grafana Alert | Memory growing unbounded, event listener leaks |
| [04-undo-redo-corruption.md](scenarios/04-undo-redo-corruption.md) | Customer Escalation | Undo restores wrong state, history corruption |
| [05-startup-database-errors.md](scenarios/05-startup-database-errors.md) | Deploy Failure | Application fails to start, configuration issues |

These scenarios describe **symptoms only** - use them to practice realistic debugging workflows.

## Success Criteria

- All 259 tests pass
- Application starts without errors
- No security vulnerabilities detected
- WebSocket connections work properly

## Reward Function

```
Pass Rate → Reward
< 50%  → 0.00
≥ 50%  → 0.15
≥ 75%  → 0.35
≥ 90%  → 0.65
100%   → 1.00
```

Additional bonuses:
- Category completion: +0.05 per fully passing category
- Bug fix bonus: up to +0.15 for fixing specific bugs
- Efficiency bonus: +0.05 for fast completion (only at 100%)
- Regression penalty: -0.15 for breaking previously passing tests

Good luck!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Cursor trails, CRDT compaction, viewport loading, element locking API, SQLite support |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Template Library Service, Export Engine, Comment & Annotation System |

These tasks test different software engineering skills while using the same codebase.
