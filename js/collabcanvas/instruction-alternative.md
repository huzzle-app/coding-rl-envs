# CollabCanvas - Alternative Tasks

## Overview

These 5 alternative tasks represent realistic software engineering challenges in the CollabCanvas real-time collaboration platform. Each task focuses on a different skill area: feature development, refactoring, performance optimization, API extension, and database migration. Complete any of these tasks to demonstrate expertise in collaborative system design.

## Environment

- **Language**: JavaScript (Node.js)
- **Infrastructure**: Express.js, Socket.io, PostgreSQL, Redis
- **Difficulty**: Senior Engineer
- **Task Types**: Feature, Refactor, Optimize, API Extension, Migration

## Tasks

### Task 1: Collaborative Cursor Trails (Feature Development)

Implement a cursor trail feature that tracks the last N cursor positions for each active user and broadcasts them to other collaborators. Trails should fade over time and be configurable per-board, integrating with the existing presence tracking system. Cursor trail data is ephemeral (not persisted) and should automatically clean up when users disconnect.

**Key Requirements**: Last 20 positions per user, 3-second pruning, 30 Hz broadcast rate, configurable `cursorTrailsEnabled` flag, linear memory scaling.

---

### Task 2: CRDT Operation Compaction (Refactoring)

Refactor the CRDT service to implement operation compaction that merges sequential operations on the same element within 500ms into compound operations. This reduces operation log size while maintaining causal ordering guarantees. Compaction must preserve undo/redo semantics and handle concurrent operations from different users correctly.

**Key Requirements**: 500ms window, vector clock preservation, compound operation atomicity, 40%+ log size reduction, conflict resolution integrity.

---

### Task 3: Viewport-Based Element Loading (Performance Optimization)

Implement viewport-based element loading that only fetches elements within the visible canvas area plus a configurable buffer zone. As users pan or zoom, dynamically load/unload elements. Off-screen elements should be represented by lightweight placeholder data that updates correctly with real-time sync.

**Key Requirements**: 500px buffer zone, lazy loading on pan/zoom, zoom-aware element loading, bounding box placeholders, 10-second downgrade delay, mixed full/placeholder state handling.

---

### Task 4: Element Locking REST API (API Extension)

Extend the REST API to support element locking operations with proper authentication and authorization. The API must support locking individual elements, bulk locking multiple elements, and querying lock status. Lock ownership must be consistent between WebSocket sessions and API clients, with proper expiration handling.

**Key Requirements**: POST/DELETE lock endpoints, bulk lock operation, lock status queries, mutual exclusion between API and WebSocket locks, 30-second expiration, editor-level permissions.

---

### Task 5: SQLite to PostgreSQL Migration Support (Migration)

Implement database abstraction that allows the application to run with either PostgreSQL or SQLite based on environment configuration. Adapt Sequelize models to handle dialect differences like JSONB columns and UUID generation strategies. The migration system should detect the target database and apply appropriate schema changes.

**Key Requirements**: `DB_DIALECT` environment switch, JSONB to JSON degradation, UUID compatibility, dialect-specific migration support, connection pooling adjustment.

---

## Getting Started

```bash
# Install dependencies
npm install

# Start infrastructure (PostgreSQL, Redis)
docker compose up -d

# Run tests
npm test
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). All tests must pass for the completed task(s).
