# CollabCanvas - Alternative Task Specifications

This document contains alternative tasks for the CollabCanvas real-time collaborative whiteboard platform. Each task represents a realistic software engineering challenge that exercises the codebase without revealing specific implementation details.

---

## Task 1: Collaborative Cursor Trails (Feature Development)

### Description

Users have requested the ability to see cursor movement trails when collaborators are actively drawing or moving elements. Currently, the presence system only shows static cursor positions, which makes it difficult to understand what other users are doing in real-time.

Implement a cursor trail feature that tracks the last N cursor positions for each active user and broadcasts them to other collaborators. The trails should fade over time and be configurable per-board. This feature should integrate with the existing presence tracking system and leverage the WebSocket infrastructure already in place.

The cursor trail data should be ephemeral (not persisted to the database) and should automatically clean up when users disconnect. Consider memory implications when many users are active on the same board simultaneously.

### Acceptance Criteria

- Cursor trails show the last 20 positions for each active user on a board
- Trail positions include timestamps and are pruned after 3 seconds
- Trail updates are broadcast via WebSocket at a maximum rate of 30 updates per second per user
- Board settings include a `cursorTrailsEnabled` boolean flag (default: true)
- Trails are automatically cleaned up when users leave the board or disconnect
- Memory usage scales linearly with active user count, not total cursor events
- Trail data structure includes: userId, positions array (x, y, timestamp), color

### Test Command

```bash
npm test
```

---

## Task 2: CRDT Operation Compaction (Refactoring)

### Description

The current CRDT implementation stores every individual operation in the operation log, which causes performance degradation for boards with extensive edit history. As boards accumulate thousands of operations, state reconstruction becomes increasingly slow.

Refactor the CRDT service to implement operation compaction. When multiple sequential operations affect the same element by the same user within a short time window (e.g., 500ms), they should be merged into a single compound operation. This reduces the operation log size while maintaining causal ordering guarantees.

The compaction logic should preserve the ability to undo/redo individual user actions while treating rapid sequential edits as a single atomic change. Special care must be taken to handle concurrent operations from different users correctly during compaction.

### Acceptance Criteria

- Sequential operations on the same element within 500ms are merged into one compound operation
- Compound operations maintain proper vector clock semantics
- Undo/redo treats compacted operations as single units
- Operations from different users are never compacted together
- Delete operations are never compacted with create/update operations
- Compaction reduces operation log size by at least 40% for typical drawing workflows
- All existing CRDT conflict resolution behavior is preserved
- Compacted operations can still be properly ordered against concurrent remote operations

### Test Command

```bash
npm test
```

---

## Task 3: Viewport-Based Element Loading (Performance Optimization)

### Description

Large boards with hundreds of elements experience significant loading delays because the system fetches all elements regardless of whether they are visible in the user's current viewport. This affects initial board load time and consumes unnecessary bandwidth.

Implement viewport-based element loading that only fetches elements within the visible canvas area plus a configurable buffer zone. As users pan or zoom, the system should dynamically load/unload elements. Elements outside the viewport should be represented by lightweight placeholder data until they come into view.

This optimization must integrate correctly with the real-time sync system so that updates to off-screen elements are still received and applied, but full element data is only loaded when needed.

### Acceptance Criteria

- Initial board load only fetches elements within viewport plus 500px buffer
- Panning triggers lazy loading of elements entering the viewport
- Zoom level affects the number of elements loaded (zoomed out = more elements visible)
- Off-screen elements are represented by bounding box placeholders (id, x, y, width, height only)
- Real-time updates to off-screen elements update placeholder bounds correctly
- Full element data is fetched when elements enter the viewport
- Elements leaving the viewport are downgraded to placeholders after 10 seconds
- Board state cache correctly handles mixed full/placeholder element data

### Test Command

```bash
npm test
```

---

## Task 4: Element Locking REST API (API Extension)

### Description

The current element locking mechanism only works through WebSocket connections. External integrations and automation tools need the ability to lock and unlock elements via REST API. This is particularly important for workflow systems that need to prevent edits during approval processes.

Extend the REST API to support element locking operations with proper authentication and authorization. The API should support locking individual elements, bulk locking multiple elements, and querying lock status. Lock ownership must be trackable to both WebSocket sessions and API clients.

The API must handle the case where a WebSocket-connected user tries to edit an element locked via API, and vice versa. Lock expiration should work consistently regardless of how the lock was acquired.

### Acceptance Criteria

- POST `/boards/:boardId/elements/:elementId/lock` acquires an element lock
- DELETE `/boards/:boardId/elements/:elementId/lock` releases an element lock
- POST `/boards/:boardId/elements/bulk-lock` locks multiple elements atomically
- GET `/boards/:boardId/elements/:elementId/lock` returns current lock status and owner
- API locks and WebSocket locks are mutually exclusive and consistent
- Lock owner is identified by user ID plus client type (api/websocket)
- All lock endpoints require editor-level board permissions
- Lock expiration (30 seconds) works identically for API and WebSocket locks

### Test Command

```bash
npm test
```

---

## Task 5: SQLite to PostgreSQL Migration Support (Migration)

### Description

CollabCanvas currently uses PostgreSQL for all environments, but some enterprise customers want to run a lightweight single-node deployment using SQLite for development and small team use cases. The application should support both database backends with a runtime configuration switch.

Implement database abstraction that allows the application to run with either PostgreSQL or SQLite based on environment configuration. This requires adapting the Sequelize models to handle dialect differences, particularly around JSONB columns (PostgreSQL) vs JSON columns (SQLite), and UUID generation strategies.

The migration system should detect the target database and apply appropriate schema changes. Existing PostgreSQL deployments must continue to work without modification.

### Acceptance Criteria

- Environment variable `DB_DIALECT` switches between 'postgres' and 'sqlite'
- JSONB columns gracefully degrade to JSON type on SQLite
- UUID primary keys work on both databases (native UUID on Postgres, string on SQLite)
- All existing migrations work on both database types
- Board settings and canvas state JSONB queries work on both databases
- Connection pooling is disabled for SQLite (single connection)
- All indexes are created appropriately for each database dialect
- Test suite can run against either database backend

### Test Command

```bash
npm test
```
