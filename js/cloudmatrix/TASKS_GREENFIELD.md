# CloudMatrix - Greenfield Implementation Tasks

These tasks require implementing **new modules from scratch** while following CloudMatrix's existing architectural patterns. Each task involves creating a new service with full test coverage.

**Test Command**: `npm test`

---

## Task 1: Usage Analytics Aggregator Service

### Overview

Implement a **UsageAnalyticsAggregator** service that collects, aggregates, and reports usage metrics across all CloudMatrix services. This service tracks document operations, collaboration sessions, storage consumption, and API usage patterns to provide insights for billing, capacity planning, and feature adoption analysis.

### Service Location

```
services/usage-aggregator/
  src/
    index.js           # Express app entry point
    config.js          # Service configuration
    services/
      aggregator.js    # Main aggregator service class
      rollup.js        # Time-series rollup logic
      quota.js         # Quota tracking and enforcement
```

### Interface Contract

```javascript
/**
 * UsageAnalyticsAggregator - Aggregates usage metrics across CloudMatrix services
 *
 * @class
 */
class UsageAnalyticsAggregator {
  /**
   * @param {Object} options - Configuration options
   * @param {Object} options.redis - Redis client for caching and pub/sub
   * @param {Object} options.db - PostgreSQL connection pool
   * @param {Object} options.eventBus - RabbitMQ event bus client
   */
  constructor(options) {}

  /**
   * Record a usage event for aggregation
   *
   * @param {UsageEvent} event - The usage event to record
   * @returns {Promise<{recorded: boolean, eventId: string}>}
   * @throws {ValidationError} If event data is invalid
   */
  async recordEvent(event) {}

  /**
   * Get aggregated usage metrics for a time range
   *
   * @param {string} organizationId - Organization identifier
   * @param {AggregationQuery} query - Query parameters
   * @returns {Promise<AggregatedMetrics>}
   */
  async getAggregatedMetrics(organizationId, query) {}

  /**
   * Get current quota status for an organization
   *
   * @param {string} organizationId - Organization identifier
   * @returns {Promise<QuotaStatus>}
   */
  async getQuotaStatus(organizationId) {}

  /**
   * Check if an operation would exceed quota limits
   *
   * @param {string} organizationId - Organization identifier
   * @param {string} metricType - Type of metric (storage, api_calls, collaborators)
   * @param {number} amount - Amount to add
   * @returns {Promise<{allowed: boolean, remaining: number, limit: number}>}
   */
  async checkQuota(organizationId, metricType, amount) {}

  /**
   * Perform time-series rollup for a metric
   * Aggregates granular data into hourly/daily/monthly buckets
   *
   * @param {string} metricType - Type of metric to roll up
   * @param {Date} cutoffTime - Roll up data older than this time
   * @returns {Promise<{rolledUp: number, errors: number}>}
   */
  async rollupMetrics(metricType, cutoffTime) {}

  /**
   * Generate usage report for billing period
   *
   * @param {string} organizationId - Organization identifier
   * @param {Date} periodStart - Billing period start
   * @param {Date} periodEnd - Billing period end
   * @returns {Promise<UsageReport>}
   */
  async generateUsageReport(organizationId, periodStart, periodEnd) {}

  /**
   * Get real-time usage dashboard data
   *
   * @param {string} organizationId - Organization identifier
   * @returns {Promise<DashboardData>}
   */
  async getDashboardData(organizationId) {}

  /**
   * Subscribe to quota threshold alerts
   *
   * @param {string} organizationId - Organization identifier
   * @param {QuotaAlertConfig} config - Alert configuration
   * @returns {Promise<{subscriptionId: string}>}
   */
  async subscribeToQuotaAlerts(organizationId, config) {}
}

module.exports = { UsageAnalyticsAggregator };
```

### Required Data Models

```javascript
/**
 * @typedef {Object} UsageEvent
 * @property {string} eventId - Unique event identifier
 * @property {string} organizationId - Organization identifier
 * @property {string} userId - User who triggered the event
 * @property {string} eventType - Type of event (document.created, api.call, storage.upload, etc.)
 * @property {string} resourceId - ID of the affected resource
 * @property {string} resourceType - Type of resource (document, file, comment, etc.)
 * @property {number} quantity - Numeric value (bytes, count, etc.)
 * @property {Object} metadata - Additional event-specific data
 * @property {Date} timestamp - When the event occurred
 */

/**
 * @typedef {Object} AggregationQuery
 * @property {Date} startTime - Start of time range
 * @property {Date} endTime - End of time range
 * @property {string} granularity - 'minute' | 'hour' | 'day' | 'month'
 * @property {string[]} metricTypes - Types of metrics to include
 * @property {string[]} [dimensions] - Group by dimensions (userId, resourceType, etc.)
 */

/**
 * @typedef {Object} AggregatedMetrics
 * @property {string} organizationId
 * @property {Date} startTime
 * @property {Date} endTime
 * @property {string} granularity
 * @property {MetricDataPoint[]} dataPoints
 * @property {Object} totals - Totals for each metric type
 */

/**
 * @typedef {Object} MetricDataPoint
 * @property {Date} timestamp
 * @property {string} metricType
 * @property {number} value
 * @property {Object} dimensions - Dimension values for this data point
 */

/**
 * @typedef {Object} QuotaStatus
 * @property {string} organizationId
 * @property {string} plan - Current subscription plan
 * @property {QuotaMetric[]} metrics
 * @property {Date} periodStart
 * @property {Date} periodEnd
 */

/**
 * @typedef {Object} QuotaMetric
 * @property {string} metricType
 * @property {number} used
 * @property {number} limit
 * @property {number} percentage - Usage percentage (0-100)
 * @property {boolean} exceeded
 */

/**
 * @typedef {Object} UsageReport
 * @property {string} reportId
 * @property {string} organizationId
 * @property {Date} periodStart
 * @property {Date} periodEnd
 * @property {Object} summary - High-level usage summary
 * @property {Object[]} lineItems - Detailed usage line items for billing
 * @property {Date} generatedAt
 */

/**
 * @typedef {Object} DashboardData
 * @property {Object} currentPeriod - Usage in current billing period
 * @property {Object} trends - Usage trends (week-over-week, month-over-month)
 * @property {Object[]} topUsers - Most active users
 * @property {Object[]} topDocuments - Most accessed documents
 * @property {Object} realtime - Real-time metrics (active users, open documents)
 */

/**
 * @typedef {Object} QuotaAlertConfig
 * @property {string} metricType - Metric to monitor
 * @property {number} threshold - Percentage threshold (0-100)
 * @property {string[]} notificationChannels - ['email', 'webhook', 'in_app']
 */
```

### Architectural Requirements

1. **Event-Driven Ingestion**: Subscribe to RabbitMQ events from other services (documents, storage, presence, etc.)
2. **Redis Caching**: Use Redis for real-time counters and recent metrics caching
3. **Time-Series Storage**: Store aggregated metrics in PostgreSQL with proper indexing for time-range queries
4. **Rollup Jobs**: Implement background jobs that roll up granular data into coarser time buckets
5. **Distributed Counting**: Use Redis HyperLogLog for unique user counts, sorted sets for rate limiting
6. **Idempotency**: Handle duplicate events gracefully using event IDs

### Acceptance Criteria

1. **Unit Tests** (minimum 25 tests):
   - Event validation and recording
   - Aggregation query building and execution
   - Quota calculation logic
   - Rollup algorithm correctness
   - Report generation

2. **Integration Tests** (minimum 10 tests):
   - Event bus subscription and processing
   - Redis counter operations
   - PostgreSQL aggregation queries
   - End-to-end metric flow

3. **Test File Location**: `tests/unit/usage-aggregator/aggregator.test.js`

4. **Coverage Requirements**:
   - All public methods must have tests
   - Edge cases: empty data, quota exceeded, rollup boundary conditions
   - Concurrent event recording must be safe

---

## Task 2: Team Management Service

### Overview

Implement a **TeamManagementService** that handles team creation, membership, roles, and hierarchical organization structures. This service manages the relationship between users, teams, and organizations, supporting features like team-based document sharing, role inheritance, and invitation workflows.

### Service Location

```
services/teams/
  src/
    index.js           # Express app entry point
    config.js          # Service configuration
    services/
      team.js          # Main team service class
      membership.js    # Membership management
      invitation.js    # Invitation handling
      hierarchy.js     # Org hierarchy logic
```

### Interface Contract

```javascript
/**
 * TeamManagementService - Manages teams, memberships, and organizational hierarchy
 *
 * @class
 */
class TeamManagementService {
  /**
   * @param {Object} options - Configuration options
   * @param {Object} options.db - PostgreSQL connection pool
   * @param {Object} options.redis - Redis client for caching
   * @param {Object} options.eventBus - RabbitMQ event bus
   * @param {Object} options.emailClient - Email service client
   */
  constructor(options) {}

  /**
   * Create a new team within an organization
   *
   * @param {CreateTeamRequest} request - Team creation data
   * @returns {Promise<Team>}
   * @throws {ValidationError} If team data is invalid
   * @throws {QuotaExceededError} If organization has reached team limit
   */
  async createTeam(request) {}

  /**
   * Get team by ID with optional member loading
   *
   * @param {string} teamId - Team identifier
   * @param {Object} options - Query options
   * @param {boolean} [options.includeMembers=false] - Include member list
   * @param {boolean} [options.includeSubteams=false] - Include subteams
   * @returns {Promise<Team|null>}
   */
  async getTeam(teamId, options = {}) {}

  /**
   * Update team properties
   *
   * @param {string} teamId - Team identifier
   * @param {UpdateTeamRequest} updates - Properties to update
   * @param {string} actorUserId - User performing the update
   * @returns {Promise<Team>}
   * @throws {ForbiddenError} If actor lacks permission
   */
  async updateTeam(teamId, updates, actorUserId) {}

  /**
   * Delete a team and handle member reassignment
   *
   * @param {string} teamId - Team identifier
   * @param {DeleteTeamOptions} options - Deletion options
   * @returns {Promise<{deleted: boolean, membersReassigned: number}>}
   */
  async deleteTeam(teamId, options) {}

  /**
   * Add a member to a team
   *
   * @param {string} teamId - Team identifier
   * @param {string} userId - User to add
   * @param {string} role - Role within team ('member', 'admin', 'owner')
   * @param {string} actorUserId - User performing the action
   * @returns {Promise<TeamMembership>}
   * @throws {ConflictError} If user is already a member
   */
  async addMember(teamId, userId, role, actorUserId) {}

  /**
   * Remove a member from a team
   *
   * @param {string} teamId - Team identifier
   * @param {string} userId - User to remove
   * @param {string} actorUserId - User performing the action
   * @returns {Promise<{removed: boolean}>}
   * @throws {ForbiddenError} If trying to remove last owner
   */
  async removeMember(teamId, userId, actorUserId) {}

  /**
   * Update a member's role within a team
   *
   * @param {string} teamId - Team identifier
   * @param {string} userId - User to update
   * @param {string} newRole - New role
   * @param {string} actorUserId - User performing the action
   * @returns {Promise<TeamMembership>}
   */
  async updateMemberRole(teamId, userId, newRole, actorUserId) {}

  /**
   * Create and send a team invitation
   *
   * @param {InvitationRequest} request - Invitation details
   * @returns {Promise<TeamInvitation>}
   */
  async createInvitation(request) {}

  /**
   * Accept a team invitation
   *
   * @param {string} invitationToken - Invitation token
   * @param {string} userId - User accepting the invitation
   * @returns {Promise<TeamMembership>}
   * @throws {ExpiredError} If invitation has expired
   * @throws {InvalidTokenError} If token is invalid
   */
  async acceptInvitation(invitationToken, userId) {}

  /**
   * Get all teams a user belongs to
   *
   * @param {string} userId - User identifier
   * @param {Object} options - Query options
   * @returns {Promise<TeamMembership[]>}
   */
  async getUserTeams(userId, options = {}) {}

  /**
   * Get organizational hierarchy starting from a team
   *
   * @param {string} teamId - Starting team identifier
   * @param {string} direction - 'ancestors' | 'descendants' | 'both'
   * @returns {Promise<TeamHierarchy>}
   */
  async getHierarchy(teamId, direction = 'both') {}

  /**
   * Move a team to a new parent in the hierarchy
   *
   * @param {string} teamId - Team to move
   * @param {string} newParentId - New parent team ID (null for root)
   * @param {string} actorUserId - User performing the action
   * @returns {Promise<Team>}
   * @throws {CycleError} If move would create a cycle
   */
  async moveTeam(teamId, newParentId, actorUserId) {}

  /**
   * Check if a user has a specific permission within a team context
   *
   * @param {string} teamId - Team context
   * @param {string} userId - User to check
   * @param {string} permission - Permission to check
   * @returns {Promise<{allowed: boolean, reason: string}>}
   */
  async checkPermission(teamId, userId, permission) {}

  /**
   * Get effective permissions for a user in a team (including inherited)
   *
   * @param {string} teamId - Team identifier
   * @param {string} userId - User identifier
   * @returns {Promise<EffectivePermissions>}
   */
  async getEffectivePermissions(teamId, userId) {}
}

module.exports = { TeamManagementService };
```

### Required Data Models

```javascript
/**
 * @typedef {Object} Team
 * @property {string} id - Unique team identifier
 * @property {string} organizationId - Parent organization
 * @property {string} name - Team display name
 * @property {string} [description] - Team description
 * @property {string} [parentTeamId] - Parent team for hierarchy
 * @property {string} visibility - 'public' | 'private' | 'secret'
 * @property {Object} settings - Team-specific settings
 * @property {Date} createdAt
 * @property {Date} updatedAt
 * @property {string} createdBy - User who created the team
 * @property {TeamMembership[]} [members] - Loaded if requested
 * @property {Team[]} [subteams] - Loaded if requested
 */

/**
 * @typedef {Object} CreateTeamRequest
 * @property {string} organizationId - Organization to create team in
 * @property {string} name - Team name
 * @property {string} [description] - Team description
 * @property {string} [parentTeamId] - Parent team for nesting
 * @property {string} visibility - 'public' | 'private' | 'secret'
 * @property {string} creatorUserId - User creating the team
 */

/**
 * @typedef {Object} UpdateTeamRequest
 * @property {string} [name] - New team name
 * @property {string} [description] - New description
 * @property {string} [visibility] - New visibility
 * @property {Object} [settings] - Settings to merge
 */

/**
 * @typedef {Object} TeamMembership
 * @property {string} teamId
 * @property {string} userId
 * @property {string} role - 'member' | 'admin' | 'owner'
 * @property {Date} joinedAt
 * @property {string} addedBy - User who added this member
 * @property {Object} [user] - User details if loaded
 */

/**
 * @typedef {Object} TeamInvitation
 * @property {string} id - Invitation identifier
 * @property {string} teamId - Team being invited to
 * @property {string} email - Invitee email address
 * @property {string} role - Role to grant upon acceptance
 * @property {string} token - Secure invitation token
 * @property {string} invitedBy - User who sent the invitation
 * @property {Date} createdAt
 * @property {Date} expiresAt
 * @property {'pending' | 'accepted' | 'expired' | 'revoked'} status
 */

/**
 * @typedef {Object} InvitationRequest
 * @property {string} teamId - Team to invite to
 * @property {string} email - Email address to invite
 * @property {string} role - Role to grant
 * @property {string} inviterUserId - User sending the invitation
 * @property {string} [message] - Personal message to include
 */

/**
 * @typedef {Object} DeleteTeamOptions
 * @property {string} actorUserId - User performing deletion
 * @property {string} [reassignTo] - Team to move members to
 * @property {boolean} [deleteSubteams=false] - Also delete subteams
 */

/**
 * @typedef {Object} TeamHierarchy
 * @property {Team} team - The focal team
 * @property {Team[]} ancestors - Parent chain up to root
 * @property {TeamHierarchyNode[]} descendants - Tree of subteams
 */

/**
 * @typedef {Object} TeamHierarchyNode
 * @property {Team} team
 * @property {TeamHierarchyNode[]} children
 * @property {number} depth
 */

/**
 * @typedef {Object} EffectivePermissions
 * @property {string} teamId
 * @property {string} userId
 * @property {string[]} permissions - List of granted permissions
 * @property {Object} sources - Where each permission comes from (direct, inherited, etc.)
 */
```

### Architectural Requirements

1. **Event Publishing**: Emit events for team changes (team.created, member.added, invitation.sent, etc.)
2. **Permission Caching**: Cache effective permissions in Redis with proper invalidation
3. **Hierarchy Queries**: Use PostgreSQL recursive CTEs for efficient hierarchy traversal
4. **Invitation Security**: Generate cryptographically secure tokens, enforce expiration
5. **Role Inheritance**: Implement permission inheritance through team hierarchy
6. **Cycle Prevention**: Detect and prevent cycles when moving teams in hierarchy

### Acceptance Criteria

1. **Unit Tests** (minimum 30 tests):
   - Team CRUD operations
   - Membership management
   - Invitation workflow (create, accept, expire, revoke)
   - Hierarchy traversal and manipulation
   - Permission checking with inheritance
   - Cycle detection

2. **Integration Tests** (minimum 12 tests):
   - Database operations with transactions
   - Event publishing
   - Cache invalidation
   - Email sending for invitations

3. **Test File Location**: `tests/unit/teams/team.test.js`, `tests/unit/teams/membership.test.js`

4. **Coverage Requirements**:
   - All public methods must have tests
   - Edge cases: empty teams, deep hierarchies, concurrent membership changes
   - Permission inheritance scenarios

---

## Task 3: Webhook Delivery System

### Overview

Implement a **WebhookDeliverySystem** that reliably delivers event notifications to external webhook endpoints. This service handles webhook registration, payload signing, delivery with retries, and delivery status tracking. It must guarantee at-least-once delivery with proper retry backoff and circuit breaking for unhealthy endpoints.

### Service Location

```
services/webhook-delivery/
  src/
    index.js           # Express app entry point
    config.js          # Service configuration
    services/
      delivery.js      # Main delivery service class
      signing.js       # Payload signing logic
      circuit.js       # Circuit breaker implementation
      queue.js         # Delivery queue management
```

### Interface Contract

```javascript
/**
 * WebhookDeliverySystem - Reliable webhook delivery with retries and circuit breaking
 *
 * @class
 */
class WebhookDeliverySystem {
  /**
   * @param {Object} options - Configuration options
   * @param {Object} options.db - PostgreSQL connection pool
   * @param {Object} options.redis - Redis client for queuing
   * @param {Object} options.eventBus - RabbitMQ for event subscription
   * @param {Object} options.httpClient - HTTP client for deliveries
   */
  constructor(options) {}

  /**
   * Register a new webhook endpoint
   *
   * @param {WebhookRegistration} registration - Webhook configuration
   * @returns {Promise<Webhook>}
   * @throws {ValidationError} If URL is invalid or events are unknown
   */
  async registerWebhook(registration) {}

  /**
   * Get webhook by ID
   *
   * @param {string} webhookId - Webhook identifier
   * @returns {Promise<Webhook|null>}
   */
  async getWebhook(webhookId) {}

  /**
   * Update webhook configuration
   *
   * @param {string} webhookId - Webhook identifier
   * @param {WebhookUpdate} updates - Properties to update
   * @returns {Promise<Webhook>}
   */
  async updateWebhook(webhookId, updates) {}

  /**
   * Delete a webhook and cancel pending deliveries
   *
   * @param {string} webhookId - Webhook identifier
   * @returns {Promise<{deleted: boolean, cancelledDeliveries: number}>}
   */
  async deleteWebhook(webhookId) {}

  /**
   * List webhooks for an organization
   *
   * @param {string} organizationId - Organization identifier
   * @param {Object} options - Pagination and filter options
   * @returns {Promise<{webhooks: Webhook[], total: number, hasMore: boolean}>}
   */
  async listWebhooks(organizationId, options = {}) {}

  /**
   * Enqueue an event for delivery to all matching webhooks
   *
   * @param {WebhookEvent} event - Event to deliver
   * @returns {Promise<{queued: number, webhookIds: string[]}>}
   */
  async enqueueEvent(event) {}

  /**
   * Attempt delivery to a specific webhook
   *
   * @param {string} deliveryId - Delivery identifier
   * @returns {Promise<DeliveryResult>}
   */
  async attemptDelivery(deliveryId) {}

  /**
   * Process the delivery queue (called by worker)
   *
   * @param {number} batchSize - Number of deliveries to process
   * @returns {Promise<{processed: number, succeeded: number, failed: number}>}
   */
  async processQueue(batchSize = 10) {}

  /**
   * Get delivery status for an event
   *
   * @param {string} eventId - Event identifier
   * @returns {Promise<EventDeliveryStatus>}
   */
  async getEventDeliveryStatus(eventId) {}

  /**
   * Get delivery history for a webhook
   *
   * @param {string} webhookId - Webhook identifier
   * @param {Object} options - Pagination options
   * @returns {Promise<{deliveries: Delivery[], total: number}>}
   */
  async getDeliveryHistory(webhookId, options = {}) {}

  /**
   * Retry a failed delivery manually
   *
   * @param {string} deliveryId - Delivery identifier
   * @returns {Promise<DeliveryResult>}
   */
  async retryDelivery(deliveryId) {}

  /**
   * Send a test event to verify webhook configuration
   *
   * @param {string} webhookId - Webhook to test
   * @returns {Promise<DeliveryResult>}
   */
  async sendTestEvent(webhookId) {}

  /**
   * Get circuit breaker status for a webhook
   *
   * @param {string} webhookId - Webhook identifier
   * @returns {Promise<CircuitState>}
   */
  async getCircuitState(webhookId) {}

  /**
   * Reset circuit breaker for a webhook (manual recovery)
   *
   * @param {string} webhookId - Webhook identifier
   * @returns {Promise<{reset: boolean}>}
   */
  async resetCircuit(webhookId) {}

  /**
   * Get webhook health metrics
   *
   * @param {string} webhookId - Webhook identifier
   * @param {Object} timeRange - Time range for metrics
   * @returns {Promise<WebhookHealthMetrics>}
   */
  async getHealthMetrics(webhookId, timeRange) {}

  /**
   * Sign a webhook payload
   *
   * @param {Object} payload - Payload to sign
   * @param {string} secret - Webhook secret
   * @param {number} timestamp - Unix timestamp
   * @returns {string} Signature string
   */
  signPayload(payload, secret, timestamp) {}

  /**
   * Verify a webhook signature (for documentation/SDK use)
   *
   * @param {Object} payload - Received payload
   * @param {string} signature - Received signature
   * @param {string} secret - Webhook secret
   * @param {number} timestamp - Received timestamp
   * @param {number} [tolerance=300] - Max age in seconds
   * @returns {boolean}
   */
  verifySignature(payload, signature, secret, timestamp, tolerance = 300) {}
}

module.exports = { WebhookDeliverySystem };
```

### Required Data Models

```javascript
/**
 * @typedef {Object} Webhook
 * @property {string} id - Unique webhook identifier
 * @property {string} organizationId - Owning organization
 * @property {string} url - Delivery endpoint URL (HTTPS required)
 * @property {string[]} events - Event types to deliver ('*' for all)
 * @property {string} secret - Shared secret for signing
 * @property {boolean} active - Whether webhook is enabled
 * @property {string} description - User-provided description
 * @property {Object} headers - Custom headers to include
 * @property {Date} createdAt
 * @property {Date} updatedAt
 * @property {WebhookStats} stats - Delivery statistics
 */

/**
 * @typedef {Object} WebhookRegistration
 * @property {string} organizationId - Organization creating the webhook
 * @property {string} url - Endpoint URL (must be HTTPS)
 * @property {string[]} events - Events to subscribe to
 * @property {string} [description] - Description
 * @property {Object} [headers] - Custom headers
 * @property {string} createdBy - User creating the webhook
 */

/**
 * @typedef {Object} WebhookUpdate
 * @property {string} [url] - New URL
 * @property {string[]} [events] - New event list
 * @property {boolean} [active] - Enable/disable
 * @property {string} [description] - New description
 * @property {Object} [headers] - New headers
 * @property {boolean} [rotateSecret] - Generate new secret
 */

/**
 * @typedef {Object} WebhookEvent
 * @property {string} eventId - Unique event identifier
 * @property {string} eventType - Type of event (document.created, etc.)
 * @property {string} organizationId - Source organization
 * @property {Object} data - Event payload data
 * @property {Date} occurredAt - When event occurred
 */

/**
 * @typedef {Object} Delivery
 * @property {string} id - Delivery attempt identifier
 * @property {string} webhookId - Target webhook
 * @property {string} eventId - Event being delivered
 * @property {string} status - 'pending' | 'in_progress' | 'succeeded' | 'failed' | 'cancelled'
 * @property {number} attemptNumber - Which attempt this is (1-based)
 * @property {Date} scheduledAt - When delivery should be attempted
 * @property {Date} [attemptedAt] - When attempt was made
 * @property {number} [responseStatus] - HTTP status code received
 * @property {number} [responseTimeMs] - Response time in milliseconds
 * @property {string} [errorMessage] - Error details if failed
 * @property {Date} createdAt
 */

/**
 * @typedef {Object} DeliveryResult
 * @property {string} deliveryId
 * @property {boolean} success
 * @property {number} [statusCode] - HTTP status code
 * @property {number} responseTimeMs - Time taken
 * @property {string} [error] - Error message if failed
 * @property {boolean} willRetry - Whether a retry is scheduled
 * @property {Date} [nextRetryAt] - When retry will occur
 */

/**
 * @typedef {Object} EventDeliveryStatus
 * @property {string} eventId
 * @property {Delivery[]} deliveries - All delivery attempts for this event
 * @property {Object} summary - Per-webhook status summary
 */

/**
 * @typedef {Object} CircuitState
 * @property {string} webhookId
 * @property {'closed' | 'open' | 'half_open'} state
 * @property {number} failureCount - Consecutive failures
 * @property {number} successCount - Consecutive successes (in half-open)
 * @property {Date} [lastFailure] - Time of last failure
 * @property {Date} [openedAt] - When circuit opened
 * @property {Date} [halfOpenAt] - When circuit will try half-open
 */

/**
 * @typedef {Object} WebhookStats
 * @property {number} totalDeliveries
 * @property {number} successfulDeliveries
 * @property {number} failedDeliveries
 * @property {number} averageResponseTimeMs
 * @property {Date} lastDeliveryAt
 * @property {string} lastDeliveryStatus
 */

/**
 * @typedef {Object} WebhookHealthMetrics
 * @property {number} successRate - Percentage (0-100)
 * @property {number} averageLatencyMs
 * @property {number} p95LatencyMs
 * @property {number} p99LatencyMs
 * @property {number} deliveriesInPeriod
 * @property {Object[]} errorBreakdown - Errors by type
 */
```

### Architectural Requirements

1. **At-Least-Once Delivery**: Use persistent queue with acknowledgments; retry until success or max attempts
2. **Exponential Backoff**: Implement configurable backoff (1s, 2s, 4s, 8s... up to max 1 hour)
3. **Circuit Breaker**: Open circuit after N consecutive failures; half-open after cooldown; close after M successes
4. **Payload Signing**: HMAC-SHA256 signature with timestamp to prevent replay attacks
5. **Idempotency**: Include delivery ID in payload so recipients can deduplicate
6. **Timeout Handling**: Configurable request timeout (default 30s); treat timeout as failure
7. **Concurrent Delivery**: Process multiple deliveries in parallel (configurable concurrency)

### Acceptance Criteria

1. **Unit Tests** (minimum 35 tests):
   - Webhook CRUD operations
   - Payload signing and verification
   - Circuit breaker state transitions
   - Backoff calculation
   - Queue processing logic
   - Event matching to webhooks

2. **Integration Tests** (minimum 15 tests):
   - End-to-end delivery flow
   - Retry behavior
   - Circuit breaker integration
   - Queue persistence
   - Concurrent delivery safety

3. **Test File Location**: `tests/unit/webhook-delivery/delivery.test.js`, `tests/unit/webhook-delivery/circuit.test.js`

4. **Coverage Requirements**:
   - All public methods must have tests
   - Edge cases: network timeouts, malformed responses, concurrent deliveries
   - Circuit breaker all state transitions (closed -> open, open -> half-open, half-open -> closed/open)

---

## General Requirements for All Tasks

### Code Style

- Follow existing CloudMatrix patterns (see `services/billing/src/index.js` for reference)
- Use Express.js for HTTP endpoints
- Use async/await for asynchronous operations
- Include JSDoc comments for all public methods
- Use meaningful error classes (ValidationError, NotFoundError, etc.)

### Testing Requirements

- Use Jest for testing (already configured in project)
- Follow existing test patterns (see `tests/unit/billing/subscription.test.js`)
- Mock external dependencies (Redis, PostgreSQL, RabbitMQ)
- Include both success and failure scenarios

### Integration Points

Each new service should integrate with:
- **RabbitMQ**: Subscribe to relevant events, publish service events
- **Redis**: Caching, rate limiting, distributed state
- **PostgreSQL**: Persistent storage
- **Existing Services**: Call permissions service for authorization, users service for user data

### Configuration

Each service needs a `config.js` with:
```javascript
module.exports = {
  port: process.env.PORT || <service-port>,
  databaseUrl: process.env.DATABASE_URL,
  redisHost: process.env.REDIS_HOST || 'localhost',
  redisPort: parseInt(process.env.REDIS_PORT || '6379', 10),
  rabbitmqUrl: process.env.RABBITMQ_URL || 'amqp://localhost',
  // Service-specific configuration...
};
```
