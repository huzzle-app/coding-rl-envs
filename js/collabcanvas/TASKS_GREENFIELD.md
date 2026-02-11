# CollabCanvas - Greenfield Implementation Tasks

These tasks require implementing new modules from scratch within the CollabCanvas real-time collaboration whiteboard application. Each task should follow the existing architectural patterns established in the codebase.

**Test Command:** `npm test`

---

## Task 1: Template Library Service

### Overview
Implement a Template Library Service that allows users to create, share, and instantiate pre-built board templates. Templates should capture full board state including elements, settings, and layout.

### New Files to Create

```
src/
  services/
    template/
      template.service.js      # Core template logic
  models/
    Template.js                # Sequelize model
tests/
  unit/
    services/
      template.service.test.js
  integration/
    template/
      template.integration.test.js
```

### Interface Contract

```javascript
/**
 * Template Service - Board template management
 * @file src/services/template/template.service.js
 */

const { v4: uuidv4 } = require('uuid');

class TemplateService {
  /**
   * @param {Object} sequelize - Sequelize instance
   * @param {Object} redis - Redis client for caching
   */
  constructor(sequelize, redis) {
    this.sequelize = sequelize;
    this.redis = redis;
  }

  /**
   * Create a template from an existing board
   * Must deep clone all elements and settings to avoid mutation issues
   *
   * @param {string} boardId - Source board ID
   * @param {Object} metadata - Template metadata
   * @param {string} metadata.name - Template name
   * @param {string} metadata.description - Template description
   * @param {string[]} metadata.tags - Categorization tags
   * @param {boolean} metadata.isPublic - Public visibility
   * @param {string} userId - Creator user ID
   * @returns {Promise<Template>} Created template
   * @throws {Error} If board not found or user lacks access
   */
  async createFromBoard(boardId, metadata, userId) {}

  /**
   * Instantiate a template to create a new board
   * Must deep clone template state to prevent cross-board mutations
   *
   * @param {string} templateId - Template ID to instantiate
   * @param {Object} options - Board creation options
   * @param {string} options.name - New board name
   * @param {string} options.teamId - Optional team ID
   * @param {string} userId - User creating the board
   * @returns {Promise<Board>} Newly created board
   * @throws {Error} If template not found or user lacks access
   */
  async instantiateTemplate(templateId, options, userId) {}

  /**
   * Search templates with pagination
   * Should use caching for frequently accessed public templates
   *
   * @param {Object} query - Search parameters
   * @param {string} [query.search] - Text search in name/description
   * @param {string[]} [query.tags] - Filter by tags
   * @param {boolean} [query.publicOnly] - Only public templates
   * @param {string} [query.creatorId] - Filter by creator
   * @param {number} [query.page=1] - Page number
   * @param {number} [query.limit=20] - Results per page
   * @returns {Promise<{templates: Template[], total: number, page: number}>}
   */
  async searchTemplates(query) {}

  /**
   * Update template metadata
   *
   * @param {string} templateId - Template ID
   * @param {Object} updates - Fields to update
   * @param {string} userId - User making the update
   * @returns {Promise<Template>} Updated template
   * @throws {Error} If template not found or user is not owner
   */
  async updateTemplate(templateId, updates, userId) {}

  /**
   * Delete a template
   *
   * @param {string} templateId - Template ID
   * @param {string} userId - User requesting deletion
   * @returns {Promise<boolean>} True if deleted
   * @throws {Error} If template not found or user is not owner
   */
  async deleteTemplate(templateId, userId) {}

  /**
   * Get template usage analytics
   *
   * @param {string} templateId - Template ID
   * @returns {Promise<{usageCount: number, lastUsed: Date, popularElements: Object[]}>}
   */
  async getTemplateAnalytics(templateId) {}

  /**
   * Fork a template to create user's own editable copy
   *
   * @param {string} templateId - Source template ID
   * @param {string} userId - User forking the template
   * @returns {Promise<Template>} Forked template
   */
  async forkTemplate(templateId, userId) {}
}

module.exports = TemplateService;
```

### Model Definition

```javascript
/**
 * Template Model
 * @file src/models/Template.js
 */

module.exports = (sequelize, DataTypes) => {
  const Template = sequelize.define('Template', {
    id: {
      type: DataTypes.UUID,
      defaultValue: DataTypes.UUIDV4,
      primaryKey: true,
    },
    name: {
      type: DataTypes.STRING(255),
      allowNull: false,
    },
    description: {
      type: DataTypes.TEXT,
    },
    tags: {
      type: DataTypes.ARRAY(DataTypes.STRING),
      defaultValue: [],
    },
    thumbnail: {
      type: DataTypes.TEXT,
    },
    creatorId: {
      type: DataTypes.UUID,
      allowNull: false,
      field: 'creator_id',
    },
    isPublic: {
      type: DataTypes.BOOLEAN,
      defaultValue: false,
      field: 'is_public',
    },
    forkedFromId: {
      type: DataTypes.UUID,
      field: 'forked_from_id',
    },
    canvasState: {
      type: DataTypes.JSONB,
      allowNull: false,
      field: 'canvas_state',
      comment: 'Deep-cloned board state including elements and settings',
    },
    settings: {
      type: DataTypes.JSONB,
      defaultValue: {},
    },
    usageCount: {
      type: DataTypes.INTEGER,
      defaultValue: 0,
      field: 'usage_count',
    },
    version: {
      type: DataTypes.INTEGER,
      defaultValue: 1,
    },
  }, {
    tableName: 'templates',
    indexes: [
      { fields: ['creator_id'] },
      { fields: ['is_public'] },
      { fields: ['tags'], using: 'GIN' },
      { fields: ['name'], using: 'GIN', operator: 'gin_trgm_ops' },
    ],
  });

  Template.associate = (models) => {
    Template.belongsTo(models.User, { foreignKey: 'creator_id', as: 'creator' });
    Template.belongsTo(models.Template, { foreignKey: 'forked_from_id', as: 'forkedFrom' });
  };

  return Template;
};
```

### Acceptance Criteria

1. **Unit Tests (minimum 25 tests)**
   - createFromBoard: Deep clones board state, handles missing board, validates permissions
   - instantiateTemplate: Creates board with unique IDs, handles missing template
   - searchTemplates: Pagination, text search, tag filtering, caching
   - updateTemplate/deleteTemplate: Permission validation, optimistic locking
   - forkTemplate: Creates independent copy, tracks lineage

2. **Integration Tests (minimum 10 tests)**
   - Full workflow: create template -> search -> instantiate -> verify board state
   - Cache invalidation on template updates
   - Concurrent template instantiation (no ID collisions)
   - Template forking preserves relationships

3. **Code Coverage:** Minimum 85% line coverage for template.service.js

4. **Integration Points**
   - Must integrate with existing `src/models/index.js` model loader
   - Must use existing `src/services/board/board.service.js` for board creation
   - Must follow CRDTService deep-clone patterns to avoid mutation bugs
   - Must use Redis caching pattern from BoardService

---

## Task 2: Export Engine Service

### Overview
Implement an Export Engine that renders boards to multiple formats (PNG, SVG, PDF). Must handle large boards with many elements efficiently and support partial exports (selected elements only).

### New Files to Create

```
src/
  services/
    export/
      export.service.js        # Core export orchestration
      renderers/
        svg.renderer.js        # SVG generation
        png.renderer.js        # PNG rasterization
        pdf.renderer.js        # PDF document generation
tests/
  unit/
    services/
      export.service.test.js
      svg.renderer.test.js
      png.renderer.test.js
      pdf.renderer.test.js
  integration/
    export/
      export.integration.test.js
```

### Interface Contract

```javascript
/**
 * Export Service - Board export to various formats
 * @file src/services/export/export.service.js
 */

const { EventEmitter } = require('events');

class ExportService extends EventEmitter {
  /**
   * @param {Object} options - Service configuration
   * @param {string} options.tempDir - Temporary file directory
   * @param {number} options.maxConcurrent - Max concurrent exports
   * @param {Object} options.redis - Redis client for job queue
   */
  constructor(options = {}) {
    super();
    this.tempDir = options.tempDir || '/tmp/exports';
    this.maxConcurrent = options.maxConcurrent || 3;
    this.redis = options.redis;
  }

  /**
   * Export board to specified format
   * Large exports should be queued and processed asynchronously
   *
   * @param {string} boardId - Board to export
   * @param {Object} options - Export options
   * @param {('png'|'svg'|'pdf')} options.format - Output format
   * @param {number} [options.scale=1] - Scale factor for raster formats
   * @param {string[]} [options.elementIds] - Specific elements to export (null = all)
   * @param {Object} [options.viewport] - Custom viewport bounds
   * @param {boolean} [options.includeBackground=true] - Include board background
   * @param {boolean} [options.async=false] - Queue for async processing
   * @param {string} userId - User requesting export
   * @returns {Promise<ExportResult>} Export result or job ID if async
   * @throws {Error} If board not found or export fails
   */
  async exportBoard(boardId, options, userId) {}

  /**
   * Get status of async export job
   *
   * @param {string} jobId - Export job ID
   * @returns {Promise<{status: string, progress: number, result?: ExportResult, error?: string}>}
   */
  async getExportStatus(jobId) {}

  /**
   * Cancel pending async export
   *
   * @param {string} jobId - Export job ID
   * @param {string} userId - User requesting cancellation
   * @returns {Promise<boolean>} True if cancelled
   */
  async cancelExport(jobId, userId) {}

  /**
   * Generate thumbnail for a board
   * Optimized for speed over quality
   *
   * @param {string} boardId - Board ID
   * @param {Object} options - Thumbnail options
   * @param {number} [options.width=200] - Thumbnail width
   * @param {number} [options.height=200] - Thumbnail height
   * @returns {Promise<Buffer>} PNG buffer
   */
  async generateThumbnail(boardId, options = {}) {}

  /**
   * Batch export multiple boards
   *
   * @param {string[]} boardIds - Board IDs to export
   * @param {Object} options - Export options (applied to all)
   * @param {string} userId - User requesting export
   * @returns {Promise<{jobId: string}>} Batch job ID
   */
  async batchExport(boardIds, options, userId) {}

  /**
   * Clean up old export files
   *
   * @param {number} maxAge - Max file age in milliseconds
   * @returns {Promise<number>} Number of files deleted
   */
  async cleanupExports(maxAge) {}
}

/**
 * @typedef {Object} ExportResult
 * @property {string} id - Export ID
 * @property {string} format - Output format
 * @property {string} path - File path (for file-based exports)
 * @property {Buffer} [buffer] - Data buffer (for in-memory exports)
 * @property {number} width - Output width in pixels
 * @property {number} height - Output height in pixels
 * @property {number} fileSize - File size in bytes
 * @property {Date} createdAt - Export timestamp
 */

module.exports = ExportService;
```

### Renderer Interface

```javascript
/**
 * Base Renderer Interface
 * All renderers must implement this interface
 */

class BaseRenderer {
  /**
   * Render elements to the target format
   *
   * @param {Object[]} elements - Canvas elements to render
   * @param {Object} options - Rendering options
   * @param {Object} options.viewport - Viewport bounds {x, y, width, height}
   * @param {number} options.scale - Scale factor
   * @param {string} options.backgroundColor - Background color
   * @returns {Promise<Buffer>} Rendered output
   */
  async render(elements, options) {
    throw new Error('render() must be implemented');
  }

  /**
   * Render a single element
   *
   * @param {Object} element - Element to render
   * @param {Object} context - Rendering context
   * @returns {Promise<Object>} Rendered element representation
   */
  async renderElement(element, context) {
    throw new Error('renderElement() must be implemented');
  }

  /**
   * Calculate bounds of elements
   *
   * @param {Object[]} elements - Elements to measure
   * @returns {{x: number, y: number, width: number, height: number}}
   */
  calculateBounds(elements) {}
}

module.exports = BaseRenderer;
```

### Acceptance Criteria

1. **Unit Tests (minimum 30 tests)**
   - ExportService: Format selection, async job queuing, cancellation
   - SVGRenderer: All element types (rectangle, ellipse, line, arrow, text, image, sticky, freehand)
   - PNGRenderer: Scale factor, transparency, large canvas handling
   - PDFRenderer: Multi-page support, text rendering, image embedding

2. **Integration Tests (minimum 12 tests)**
   - End-to-end export flow for each format
   - Async export with progress tracking
   - Batch export with multiple boards
   - Partial export (selected elements)
   - Export of board with 1000+ elements (performance test)

3. **Code Coverage:** Minimum 80% line coverage across all export modules

4. **Integration Points**
   - Must load board state through existing `src/models/Board.js`
   - Must respect element properties from `src/models/Element.js`
   - Must integrate with UploadService for file storage patterns
   - Must emit events compatible with existing WebSocket broadcast patterns

---

## Task 3: Comment and Annotation System

### Overview
Implement a threaded comment and annotation system that allows users to attach discussions to specific elements or canvas regions. Must support real-time updates through WebSocket integration.

### New Files to Create

```
src/
  services/
    annotation/
      annotation.service.js    # Core annotation logic
      thread.service.js        # Comment threading
  websocket/
    handlers/
      comment.handler.js       # Real-time comment updates
tests/
  unit/
    services/
      annotation.service.test.js
      thread.service.test.js
  integration/
    annotation/
      annotation.integration.test.js
  security/
    comment.security.test.js
```

### Interface Contract

```javascript
/**
 * Annotation Service - Canvas annotations and comments
 * @file src/services/annotation/annotation.service.js
 */

const { EventEmitter } = require('events');

class AnnotationService extends EventEmitter {
  /**
   * @param {Object} sequelize - Sequelize instance
   * @param {Object} redis - Redis client
   * @param {Object} presenceService - PresenceService for user info
   */
  constructor(sequelize, redis, presenceService) {
    super();
    this.sequelize = sequelize;
    this.redis = redis;
    this.presenceService = presenceService;
  }

  /**
   * Create an annotation on a board
   * Annotations can be attached to elements or canvas regions
   *
   * @param {string} boardId - Board ID
   * @param {Object} annotation - Annotation data
   * @param {('element'|'region'|'freeform')} annotation.type - Annotation type
   * @param {string} [annotation.elementId] - Target element ID (for element type)
   * @param {Object} [annotation.region] - Target region {x, y, width, height}
   * @param {Object} annotation.position - Annotation marker position {x, y}
   * @param {string} annotation.content - Initial comment content
   * @param {string} userId - Creator user ID
   * @returns {Promise<Annotation>} Created annotation with initial comment
   * @throws {Error} If board/element not found or invalid data
   */
  async createAnnotation(boardId, annotation, userId) {}

  /**
   * Add a comment to an annotation thread
   *
   * @param {string} annotationId - Annotation ID
   * @param {Object} comment - Comment data
   * @param {string} comment.content - Comment text (supports markdown)
   * @param {string} [comment.parentId] - Parent comment ID for replies
   * @param {string[]} [comment.mentions] - Mentioned user IDs
   * @param {string} userId - Commenter user ID
   * @returns {Promise<Comment>} Created comment
   * @throws {Error} If annotation not found or user lacks access
   */
  async addComment(annotationId, comment, userId) {}

  /**
   * Edit an existing comment
   * Must track edit history
   *
   * @param {string} commentId - Comment ID
   * @param {string} content - New content
   * @param {string} userId - User making the edit
   * @returns {Promise<Comment>} Updated comment with edit timestamp
   * @throws {Error} If comment not found or user is not author
   */
  async editComment(commentId, content, userId) {}

  /**
   * Delete a comment (soft delete, preserves thread structure)
   *
   * @param {string} commentId - Comment ID
   * @param {string} userId - User requesting deletion
   * @returns {Promise<boolean>} True if deleted
   */
  async deleteComment(commentId, userId) {}

  /**
   * Resolve/unresolve an annotation thread
   *
   * @param {string} annotationId - Annotation ID
   * @param {boolean} resolved - Resolution status
   * @param {string} userId - User changing status
   * @returns {Promise<Annotation>} Updated annotation
   */
  async setResolved(annotationId, resolved, userId) {}

  /**
   * Get all annotations for a board
   *
   * @param {string} boardId - Board ID
   * @param {Object} options - Query options
   * @param {boolean} [options.includeResolved=false] - Include resolved annotations
   * @param {string} [options.elementId] - Filter by element
   * @returns {Promise<Annotation[]>} Annotations with nested comments
   */
  async getBoardAnnotations(boardId, options = {}) {}

  /**
   * Get annotation thread with all comments
   *
   * @param {string} annotationId - Annotation ID
   * @returns {Promise<{annotation: Annotation, comments: Comment[]}>}
   */
  async getThread(annotationId) {}

  /**
   * Add reaction to a comment
   *
   * @param {string} commentId - Comment ID
   * @param {string} emoji - Reaction emoji
   * @param {string} userId - User adding reaction
   * @returns {Promise<{reactions: Object}>} Updated reactions
   */
  async addReaction(commentId, emoji, userId) {}

  /**
   * Remove reaction from a comment
   *
   * @param {string} commentId - Comment ID
   * @param {string} emoji - Reaction emoji to remove
   * @param {string} userId - User removing reaction
   * @returns {Promise<{reactions: Object}>} Updated reactions
   */
  async removeReaction(commentId, emoji, userId) {}

  /**
   * Get unread comment count for user on board
   *
   * @param {string} boardId - Board ID
   * @param {string} userId - User ID
   * @returns {Promise<number>} Unread count
   */
  async getUnreadCount(boardId, userId) {}

  /**
   * Mark comments as read
   *
   * @param {string[]} commentIds - Comment IDs to mark read
   * @param {string} userId - User ID
   * @returns {Promise<void>}
   */
  async markAsRead(commentIds, userId) {}
}

module.exports = AnnotationService;
```

### WebSocket Handler

```javascript
/**
 * Comment WebSocket Handler
 * @file src/websocket/handlers/comment.handler.js
 */

class CommentHandler {
  /**
   * @param {Object} io - Socket.io server instance
   * @param {Object} annotationService - AnnotationService instance
   */
  constructor(io, annotationService) {
    this.io = io;
    this.annotationService = annotationService;
  }

  /**
   * Register socket event handlers
   * Must properly clean up listeners on disconnect (see presence.service.js A3 bug)
   *
   * @param {Object} socket - Socket.io socket
   * @param {Object} user - Authenticated user
   */
  registerHandlers(socket, user) {}

  /**
   * Handle new annotation creation
   * Must broadcast to all board members
   *
   * @param {Object} socket - Socket connection
   * @param {Object} data - Annotation data
   */
  async handleNewAnnotation(socket, data) {}

  /**
   * Handle new comment in thread
   * Must notify mentioned users and thread participants
   *
   * @param {Object} socket - Socket connection
   * @param {Object} data - Comment data
   */
  async handleNewComment(socket, data) {}

  /**
   * Handle comment typing indicator
   *
   * @param {Object} socket - Socket connection
   * @param {Object} data - Typing indicator data
   */
  handleTyping(socket, data) {}

  /**
   * Handle comment resolution
   *
   * @param {Object} socket - Socket connection
   * @param {Object} data - Resolution data
   */
  async handleResolve(socket, data) {}
}

module.exports = CommentHandler;
```

### Extended Comment Model

```javascript
/**
 * Update existing Comment model to support threading
 * @file src/models/Comment.js (modifications)
 *
 * Add these fields to existing model:
 */

const additionalFields = {
  parentId: {
    type: DataTypes.UUID,
    field: 'parent_id',
    comment: 'Parent comment ID for threading',
  },
  annotationId: {
    type: DataTypes.UUID,
    field: 'annotation_id',
    comment: 'Associated annotation ID',
  },
  mentions: {
    type: DataTypes.ARRAY(DataTypes.UUID),
    defaultValue: [],
    comment: 'Mentioned user IDs',
  },
  reactions: {
    type: DataTypes.JSONB,
    defaultValue: {},
    comment: 'Emoji reactions: {emoji: [userIds]}',
  },
  editHistory: {
    type: DataTypes.JSONB,
    defaultValue: [],
    field: 'edit_history',
    comment: 'Previous versions: [{content, editedAt}]',
  },
  isDeleted: {
    type: DataTypes.BOOLEAN,
    defaultValue: false,
    field: 'is_deleted',
    comment: 'Soft delete flag',
  },
};

/**
 * New Annotation model needed
 */
const Annotation = {
  id: 'UUID PRIMARY KEY',
  boardId: 'UUID NOT NULL',
  elementId: 'UUID (nullable)',
  type: "ENUM('element', 'region', 'freeform')",
  position: 'JSONB {x, y}',
  region: 'JSONB {x, y, width, height} (nullable)',
  isResolved: 'BOOLEAN DEFAULT false',
  resolvedById: 'UUID (nullable)',
  resolvedAt: 'TIMESTAMP (nullable)',
  creatorId: 'UUID NOT NULL',
};
```

### Acceptance Criteria

1. **Unit Tests (minimum 35 tests)**
   - AnnotationService: CRUD operations, threading, resolution, reactions
   - ThreadService: Parent-child relationships, mention extraction, notification triggers
   - CommentHandler: Event registration, broadcast, cleanup on disconnect

2. **Integration Tests (minimum 15 tests)**
   - Full annotation lifecycle: create -> comment -> resolve
   - Real-time updates across multiple connected clients
   - Thread ordering and pagination
   - Mention notifications

3. **Security Tests (minimum 8 tests)**
   - XSS prevention in comment content (markdown sanitization)
   - Authorization checks for comment editing/deletion
   - Rate limiting on comment creation
   - Mention validation (can only mention board members)

4. **Code Coverage:** Minimum 85% line coverage for annotation modules

5. **Integration Points**
   - Must integrate with existing `src/models/Comment.js`
   - Must use PresenceService for user info and online status
   - Must follow BroadcastService patterns for real-time updates
   - Must avoid memory leak patterns identified in PresenceService (BUG A3)
   - Must use deep cloning patterns from CRDTService when storing state

---

## Architectural Guidelines

When implementing these tasks, follow the existing patterns in the codebase:

### Service Pattern
```javascript
// Services receive dependencies via constructor
class MyService {
  constructor(sequelize, redis, otherService) {
    this.sequelize = sequelize;
    this.redis = redis;
    this.otherService = otherService;
  }
}
```

### Error Handling
```javascript
// Use custom errors for domain-specific failures
class NotFoundError extends Error {
  constructor(resource, id) {
    super(`${resource} not found: ${id}`);
    this.code = 'NOT_FOUND';
  }
}
```

### Deep Cloning (Critical)
```javascript
// ALWAYS deep clone state to avoid mutation bugs (see B2, B4)
const clonedState = JSON.parse(JSON.stringify(state));
// Or use structuredClone for objects with Date/Map/Set
```

### Event Listener Cleanup (Critical)
```javascript
// ALWAYS store handler references and clean up on disconnect (see A3)
const handler = () => { /* ... */ };
this.handlers.set(socket.id, handler);
socket.on('event', handler);

// On cleanup:
socket.off('event', this.handlers.get(socket.id));
this.handlers.delete(socket.id);
```

### Test Organization
```javascript
// Follow existing test structure
describe('ServiceName', () => {
  let service;

  beforeEach(() => {
    service = new ServiceName(/* mocked deps */);
  });

  describe('methodName', () => {
    test('should handle normal case', () => {});
    test('should handle edge case', () => {});
    test('should throw on invalid input', () => {});
  });
});
```
