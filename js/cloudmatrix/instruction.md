# CloudMatrix - Real-Time Collaborative Workspace Platform

## Task Overview

Fix bugs in a real-time collaborative workspace platform built with Node.js microservices. CloudMatrix is a Distinguished-level environment (24-48 hours) that simulates a production-grade collaborative editing platform (think Google Docs + Figma + Notion) with complex real-time synchronization, operational transform, and distributed systems challenges.

## Known Issues

The codebase needs attention. Failures span configuration, service logic, and integration points.

## Architecture

CloudMatrix consists of 15 Node.js microservices communicating via RabbitMQ:

| Service | Port | Responsibility |
|---------|------|----------------|
| Gateway | 3000 | API routing, rate limiting, WebSocket upgrade |
| Auth | 3001 | Authentication, OAuth, JWT, session management |
| Users | 3002 | User profiles, preferences, teams |
| Documents | 3003 | Document CRUD, rich text, versioning |
| Presence | 3004 | Real-time presence, cursors, selections |
| Comments | 3005 | Threaded comments, mentions, reactions |
| Versions | 3006 | Version history, branching, merging |
| Search | 3007 | Full-text search, indexing, faceted queries |
| Notifications | 3008 | Push notifications, email, in-app |
| Storage | 3009 | File uploads, image processing, CDN |
| Analytics | 3010 | Usage analytics, engagement tracking |
| Billing | 3011 | Subscriptions, usage-based pricing |
| Permissions | 3012 | ACL, sharing, collaborative access |
| Webhooks | 3013 | Event webhooks, integrations |
| Admin | 3014 | Admin dashboard, tenant management |

## Infrastructure

- **RabbitMQ 3.13**: Message broker for inter-service communication
- **PostgreSQL 16**: Four databases (docs, users, analytics, billing)
- **Redis 7**: Caching, pub/sub, presence tracking, distributed locks
- **Consul 1.17**: Service discovery and configuration management
- **MinIO**: S3-compatible file/image storage
- **Elasticsearch 8**: Full-text search and document indexing

## Bug Categories

The issues span multiple categories typical of distributed real-time collaborative Node.js systems:

- **Setup/Configuration** (15): Circular imports, RabbitMQ connections, WebSocket setup, Elasticsearch index, service discovery
- **Real-Time Sync** (12): CRDT merge conflicts, OT composition errors, cursor offset, undo/redo corruption, state divergence
- **WebSocket Management** (10): Connection leaks, reconnection backoff, presence stale, heartbeat, message ordering
- **Document Processing** (8): Rich text delta, table cell merge, code block ReDoS, SSRF in link preview
- **Collaboration Features** (10): Cursor tracking, selection highlighting, comment anchors, track changes, collaborative lock
- **Search & Indexing** (8): Full-text injection, indexing pipeline loss, faceted overflow, permission filtering race
- **Database/Transactions** (10): Isolation levels, saga compensation, outbox duplication, N+1 queries, deadlocks
- **Auth/Permissions** (8): JWT claims, OAuth CSRF, sharing tokens, ACL inheritance, permission cache race
- **Caching/CDN** (8): Cache stampede, snapshot stale, CDN purge race, thundering herd, write-through atomicity
- **Security** (10): SQL injection, XSS, SSRF, prototype pollution, path traversal, ReDoS, IDOR
- **Event Sourcing** (8): Event ordering, idempotency collision, replay skip, projection race, snapshot corruption
- **Configuration** (8): Feature flags, JWT_SECRET validation, rate limit parsing, type coercion, Redis cluster
- **Observability** (5): Trace context, correlation IDs, metrics cardinality, health checks, log conflicts

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local development)

### Setup

```bash
cd js/cloudmatrix

# Start infrastructure and services
docker compose up -d

# Wait for services to be healthy
docker compose ps

# Run tests
npx jest --ci
```

### Initial State

The environment starts with **setup bugs** that prevent services from starting correctly. You must fix these foundational issues before the test suite can run successfully.

## Success Criteria

### Reward Function (8-Threshold, Very Sparse)

```
Pass Rate -> Reward
>= 100% -> 1.00
>= 95% -> 0.78
>= 85% -> 0.55
>= 70% -> 0.38
>= 55% -> 0.22
>= 40% -> 0.12
>= 25% -> 0.05
>= 10% -> 0.00
< 10% -> 0.00
```

**Target**: to achieve 100% test pass rate (tests) for maximum reward of 1.0.

### Test Execution

```bash
# Run full test suite
npx jest --ci

# Run specific test categories
npx jest tests/unit
npx jest tests/integration
npx jest tests/security
```

## Key Challenges

1. **Real-Time Collaboration**: CRDT merge, operational transform, cursor synchronization across 15 services
2. **Service Dependencies**: Bugs require fixes across multiple services with complex dependency chains
3. **Event Ordering**: Message-driven architecture requires careful ordering and idempotency
4. **Distributed State**: Coordination between services via RabbitMQ, Redis pub/sub, and Consul
5. **Async Complexity**: Deep async/await chains with WebSocket lifecycle management

## Tips

- Start with setup bugs (L-prefixed) to get services running
- Check RabbitMQ management UI at http://localhost:15672 (cloudmatrix/cloudmatrix)
- Monitor logs: `docker compose logs -f <service-name>`
- Use Consul UI at http://localhost:8500 for service discovery
- Use Elasticsearch Kibana at http://localhost:5601 for search debugging
- Test incrementally after each fix to avoid breaking working tests
- Follow the dependency chains: fix L1 first, then follow the graph

## Architecture Patterns

- **API Gateway**: Single entry point with request routing and WebSocket upgrade
- **Event-Driven**: Async communication via RabbitMQ exchanges and queues
- **CRDT/OT Hybrid**: Conflict-free data types with operational transform for text editing
- **Circuit Breaker**: Fault tolerance for inter-service calls
- **Saga Pattern**: Distributed transactions with compensation logic
- **Event Sourcing**: Document version history with event replay
- **CQRS**: Separate read/write models for search and analytics

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Usage-based billing, shared permissions engine, search optimization, audit logging, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Usage Analytics Aggregator, Team Management Service, Webhook Delivery System |

These tasks test different software engineering skills while using the same codebase.

Good luck debugging!
