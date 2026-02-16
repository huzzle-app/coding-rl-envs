# CollabCanvas - Real-time Collaborative Whiteboard

## Overview

CollabCanvas is a real-time collaborative whiteboard application built with Node.js, Express, Socket.io, PostgreSQL, and Redis. The codebase has bugs that you must identify and fix.

## Objective

Fix all bugs to achieve 100% test pass rate.

## Architecture

The application consists of:

- **WebSocket Layer**: Real-time collaboration via Socket.io
- **State Management**: CRDT-based conflict-free replicated data types
- **Storage**: File upload handling with validation
- **Authentication**: JWT + OAuth 2.0
- **Database**: PostgreSQL for persistence, Redis for pub/sub
- **API**: REST endpoints for board/user management

## Known Issues

Test failures indicate issues in core modules. Some infrastructure code may also need review.

## Getting Started

```bash
# Install dependencies
npm install

# Start infrastructure (PostgreSQL, Redis)
docker compose up -d

# Run tests
npm test
# or
npx jest --ci
```

## Key Challenges

### JavaScript-Specific Bugs

Many bugs exploit JavaScript's unique characteristics:

- **Type coercion**: String comparison `'10' > '9'` evaluates to false
- **Missing await**: Async operations complete after function returns
- **this binding**: Arrow functions vs regular functions in callbacks
- **Closure capture**: Event handlers capturing stale variable references
- **Prototype pollution**: Unsafe object property access without `hasOwnProperty`

### Real-time Synchronization

WebSocket handlers contain race conditions and memory leaks that only manifest with concurrent users.

#Setup Bugs (Fix First!)

The application won't start properly until these are fixed:

1. **F1**: `package.json` - socket.io version mismatch with client
2. **F2**: `src/config/index.js` - circular import with `database.js`
3. **F4**: `src/config/database.js` - `process.env.DB_POOL_SIZE` is string, not number

## Key Files

| File | Categories |
|------|-----------|
| `src/services/canvas/crdt.service.js` | State Management (B1, B2, B3) |
| `src/services/canvas/sync.service.js` | Real-time (A1, A2) |
| `src/services/canvas/history.service.js` | State Management (B4) |
| `src/services/collaboration/presence.service.js` | Real-time (A3) |
| `src/websocket/handlers/presence.handler.js` | Real-time (A4) |
| `src/services/storage/upload.service.js` | File Handling (E1-E4) |
| `src/services/auth/jwt.service.js` | Authentication (D1, D2) |
| `src/config/database.js` | Configuration (F2, F4) |

## Common Bug Patterns

- **Missing await**: Functions return before async operations complete
- **Shallow copy**: Using `{...obj}` spread operator loses nested properties
- **Type coercion**: `process.env` values are always strings, need parsing
- **Stale closures**: Event handlers capture variables by reference
- **No hasOwnProperty**: Iterating object properties without checking own properties

## Reward Function

Pass rate thresholds (sparse rewards):

| Pass Rate | Reward |
|-----------|--------|
| < 50%  | 0.00 |
| >= 50% | 0.15 |
| >= 75% | 0.35 |
| >= 90% | 0.65 |
| 100%   | 1.00 |

Additional scoring:
- **Regression penalty**: -0.15 for breaking previously passing tests
- **Category completion bonus**: +0.05 per fully passing category
- **Bug fix bonus**: Up to +0.15 for critical bug fixes

## Success Criteria

- All tests pass
- Application starts without errors
- No security vulnerabilities
- WebSocket connections function correctly
- Real-time collaboration works across multiple clients

## Tips

1. Start with setup bugs (F1, F2, F4) to get the app running
2. Fix async/await issues (A1) before race conditions (A2)
3. Look for type coercion bugs in environment variable parsing
4. Check for shallow vs deep copy issues in state management
5. Validate all user inputs in file upload and authentication flows
6. Use `hasOwnProperty()` when iterating object properties
7. Ensure proper `this` binding in callback functions
8. Close all connections/streams in error handlers

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Cursor trails, CRDT compaction, viewport loading, element locking API, SQLite support |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Template Library Service, Export Engine, Comment & Annotation System |

These tasks test different software engineering skills while using the same codebase.
