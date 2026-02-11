# CloudMatrix - Greenfield Implementation Tasks

## Overview

CloudMatrix supports three greenfield tasks that require implementing new microservices from scratch while following the platform's existing architectural patterns. Each service involves creating a new module with full test coverage, database schema integration, event publishing, and integration with existing services.

## Environment

- **Language**: JavaScript (Node.js)
- **Infrastructure**: RabbitMQ, PostgreSQL, Redis, Consul
- **Difficulty**: Distinguished (24-48 hours)

## Tasks

### Task 1: Usage Analytics Aggregator Service

Implement a **UsageAnalyticsAggregator** service that collects, aggregates, and reports usage metrics across all CloudMatrix services. This service tracks document operations, collaboration sessions, storage consumption, and API usage patterns to provide insights for billing, capacity planning, and feature adoption analysis.

**Service Interface**:
- `recordEvent(event)` — Record a usage event for aggregation
- `getAggregatedMetrics(organizationId, query)` — Get metrics for a time range with grouping
- `getQuotaStatus(organizationId)` — Get current quota usage and limits
- `checkQuota(organizationId, metricType, amount)` — Check if operation would exceed limits
- `rollupMetrics(metricType, cutoffTime)` — Aggregate granular data into hourly/daily/monthly buckets
- `generateUsageReport(organizationId, periodStart, periodEnd)` — Generate billing period report
- `getDashboardData(organizationId)` — Get real-time usage dashboard data

**Key Requirements**:
- Subscribe to RabbitMQ events from documents, storage, presence, and API services
- Use Redis for real-time counters and caching
- Store aggregated metrics in PostgreSQL with time-range query optimization
- Implement background rollup jobs
- Support 4+ usage dimensions (collaborators, storage, API calls, compute)
- Minimum 35 unit + integration tests

### Task 2: Team Management Service

Implement a **TeamManagementService** that handles team creation, membership, roles, and hierarchical organization structures. This service manages the relationship between users, teams, and organizations, supporting team-based document sharing, role inheritance, and invitation workflows.

**Service Interface**:
- `createTeam(request)` — Create a new team in an organization
- `getTeam(teamId, options)` — Get team with optional member/subteam loading
- `updateTeam(teamId, updates, actorUserId)` — Update team properties
- `deleteTeam(teamId, options)` — Delete team and handle member reassignment
- `addMember(teamId, userId, role, actorUserId)` — Add member to team
- `removeMember(teamId, userId, actorUserId)` — Remove team member
- `updateMemberRole(teamId, userId, newRole, actorUserId)` — Change member role
- `createInvitation(request)` — Send team invitation
- `acceptInvitation(invitationToken, userId)` — Accept invitation and join team
- `getUserTeams(userId, options)` — Get all teams a user belongs to
- `getHierarchy(teamId, direction)` — Get organizational hierarchy
- `moveTeam(teamId, newParentId, actorUserId)` — Move team in hierarchy with cycle detection
- `checkPermission(teamId, userId, permission)` — Check user permission in team context
- `getEffectivePermissions(teamId, userId)` — Get permissions including inherited ones

**Key Requirements**:
- Emit events for team changes (team.created, member.added, etc.)
- Cache effective permissions in Redis with proper invalidation
- Use PostgreSQL recursive CTEs for efficient hierarchy traversal
- Generate cryptographically secure invitation tokens with expiration
- Support role inheritance through team hierarchy
- Detect and prevent cycles when moving teams
- Minimum 42 unit + integration tests

### Task 3: Webhook Delivery System

Implement a **WebhookDeliverySystem** that reliably delivers event notifications to external webhook endpoints. The service handles webhook registration, payload signing, delivery with retries, and delivery status tracking, guaranteeing at-least-once delivery with proper retry backoff and circuit breaking.

**Service Interface**:
- `registerWebhook(registration)` — Register a new webhook endpoint
- `getWebhook(webhookId)` — Retrieve webhook by ID
- `updateWebhook(webhookId, updates)` — Update webhook configuration
- `deleteWebhook(webhookId)` — Delete webhook and cancel pending deliveries
- `listWebhooks(organizationId, options)` — List webhooks with pagination
- `enqueueEvent(event)` — Enqueue event for delivery to matching webhooks
- `attemptDelivery(deliveryId)` — Attempt delivery to a specific webhook
- `processQueue(batchSize)` — Process delivery queue (called by worker)
- `getEventDeliveryStatus(eventId)` — Get delivery status for an event
- `getDeliveryHistory(webhookId, options)` — Get delivery attempts for a webhook
- `retryDelivery(deliveryId)` — Manually retry a failed delivery
- `sendTestEvent(webhookId)` — Send test event to verify configuration
- `getCircuitState(webhookId)` — Get circuit breaker status
- `resetCircuit(webhookId)` — Manually reset circuit breaker
- `getHealthMetrics(webhookId, timeRange)` — Get health metrics (success rate, latency)
- `signPayload(payload, secret, timestamp)` — HMAC-SHA256 payload signing
- `verifySignature(payload, signature, secret, timestamp, tolerance)` — Verify webhook signature

**Key Requirements**:
- Persistent queue with at-least-once delivery guarantees
- Exponential backoff retry (1s, 2s, 4s, 8s... up to 1 hour)
- Circuit breaker with closed/open/half-open states
- HMAC-SHA256 payload signing with timestamp
- Idempotent delivery with delivery IDs
- Configurable timeout (default 30s), concurrent delivery
- Minimum 50 unit + integration tests

## Getting Started

```bash
cd js/cloudmatrix
docker compose up -d
npm test
```

## Success Criteria

Implementations meet the architectural requirements and acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
