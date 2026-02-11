# CollabCanvas - Greenfield Implementation Tasks

## Overview

These 3 greenfield tasks require implementing new modules from scratch within the CollabCanvas architecture. Each task involves designing and implementing a complete service with unit tests, integration tests, and proper error handling. These tasks demonstrate full-stack capability in building maintainable, tested software systems.

## Environment

- **Language**: JavaScript (Node.js)
- **Infrastructure**: Express.js, Socket.io, PostgreSQL, Redis, Sequelize ORM
- **Difficulty**: Senior Engineer
- **Task Types**: Greenfield Implementation

## Tasks

### Task 1: Template Library Service

Implement a Template Library Service that allows users to create, share, and instantiate pre-built board templates. Templates capture full board state including elements, settings, and layout.

**Interface Overview**:
- `createFromBoard(boardId, metadata, userId)` — Create template from existing board, deep clone all state
- `instantiateTemplate(templateId, options, userId)` — Create new board from template with unique IDs
- `searchTemplates(query)` — Search with pagination, text search, tag filtering, and caching
- `updateTemplate(templateId, updates, userId)` — Update metadata with owner validation
- `deleteTemplate(templateId, userId)` — Delete templates (with permission checks)
- `forkTemplate(templateId, userId)` — Create independent copy tracking lineage
- `getTemplateAnalytics(templateId)` — Usage analytics and popular elements

**New Files**: `src/services/template/template.service.js`, `src/models/Template.js`, test files

**Key Requirements**:
- Unit tests: 25+ tests covering CRUD, deep cloning, permissions
- Integration tests: 10+ tests for workflows and cache invalidation
- 85% code coverage for template.service.js
- Integration with existing BoardService and CRDTService patterns

---

### Task 2: Export Engine Service

Implement an Export Engine that renders boards to multiple formats (PNG, SVG, PDF). Must handle large boards with many elements efficiently and support partial exports.

**Interface Overview**:
- `exportBoard(boardId, options, userId)` — Export to png/svg/pdf with scale factor, element selection, async support
- `getExportStatus(jobId)` — Query async job status with progress tracking
- `cancelExport(jobId, userId)` — Cancel pending exports
- `generateThumbnail(boardId, options)` — Optimized thumbnail generation
- `batchExport(boardIds, options, userId)` — Export multiple boards
- `cleanupExports(maxAge)` — Cleanup old export files

**Renderers**:
- `SVGRenderer` — Vector rendering for all element types (rectangle, ellipse, line, arrow, text, image, sticky, freehand)
- `PNGRenderer` — Rasterization with scale factor and transparency
- `PDFRenderer` — PDF generation with multi-page support

**New Files**: `src/services/export/export.service.js`, `src/services/export/renderers/{svg,png,pdf}.renderer.js`, test files

**Key Requirements**:
- Unit tests: 30+ tests covering format selection, async queuing, renderer behavior
- Integration tests: 12+ tests for end-to-end exports and large board handling
- 80% code coverage across export modules
- EventEmitter integration for progress tracking

---

### Task 3: Comment and Annotation System

Implement a threaded comment and annotation system allowing users to attach discussions to specific elements or canvas regions. Must support real-time updates through WebSocket integration.

**Interface Overview**:
- `createAnnotation(boardId, annotation, userId)` — Create element/region/freeform annotations
- `addComment(annotationId, comment, userId)` — Add threaded comments with markdown and mentions
- `editComment(commentId, content, userId)` — Edit with history tracking
- `deleteComment(commentId, userId)` — Soft delete preserving thread structure
- `setResolved(annotationId, resolved, userId)` — Resolve/unresolve threads
- `getBoardAnnotations(boardId, options)` — Query with filtering and resolution status
- `getThread(annotationId)` — Full thread with nested comments
- `addReaction(commentId, emoji, userId)` — Emoji reactions
- `getUnreadCount(boardId, userId)` — Unread comment tracking

**WebSocket Handler**:
- Real-time annotation and comment updates
- Typing indicators
- Thread resolution broadcasts
- Proper cleanup on disconnect (avoid memory leaks)

**Models**: Extend existing Comment model with `parentId`, `annotationId`, `mentions`, `reactions`, `editHistory`, `isDeleted`. Create new Annotation model for annotation metadata.

**New Files**: `src/services/annotation/annotation.service.js`, `src/services/annotation/thread.service.js`, `src/websocket/handlers/comment.handler.js`, `src/models/Annotation.js`, test files

**Key Requirements**:
- Unit tests: 35+ tests for CRUD, threading, reactions, permissions
- Integration tests: 15+ tests for annotation lifecycle and real-time updates
- Security tests: 8+ tests for XSS prevention, authorization, rate limiting
- 85% code coverage for annotation modules
- EventEmitter integration for real-time broadcasts

---

## Architectural Patterns

Follow these patterns established in the CollabCanvas codebase:

**Service Constructor**:
```javascript
class MyService {
  constructor(sequelize, redis, otherService) {
    this.sequelize = sequelize;
    this.redis = redis;
    this.otherService = otherService;
  }
}
```

**Deep Cloning** (Critical):
```javascript
// ALWAYS deep clone state to avoid mutation bugs
const clonedState = JSON.parse(JSON.stringify(state));
// Or use structuredClone for objects with Date/Map/Set
```

**Event Listener Cleanup** (Critical):
```javascript
// Store handler references and clean up on disconnect
const handler = () => { /* ... */ };
this.handlers.set(socket.id, handler);
socket.on('event', handler);

// On cleanup:
socket.off('event', this.handlers.get(socket.id));
this.handlers.delete(socket.id);
```

**Error Handling**:
```javascript
// Use custom errors for domain-specific failures
class NotFoundError extends Error {
  constructor(resource, id) {
    super(`${resource} not found: ${id}`);
    this.code = 'NOT_FOUND';
  }
}
```

---

## Getting Started

```bash
# Install dependencies
npm install

# Start infrastructure
docker compose up -d

# Run tests
npm test
```

## Success Criteria

Implementation meets all acceptance criteria in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md). All unit, integration, and security tests must pass. Code must integrate properly with existing services and follow established architectural patterns.
