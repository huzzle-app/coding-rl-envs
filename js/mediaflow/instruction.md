# MediaFlow - Distributed Video Streaming Platform

## Task Overview

Fix bugs in a distributed video streaming platform built with Node.js microservices. MediaFlow is a Principal-level environment (8-16 hours) that simulates a production-grade video streaming service with complex distributed systems challenges.

## Known Issues

The test suite has multiple failures across core modules. Issues appear to span business logic and infrastructure layers.

## Architecture

MediaFlow consists of 10 Node.js microservices communicating via RabbitMQ:

| Service | Port | Responsibility |
|---------|------|----------------|
| Gateway | 3000 | API Gateway, request routing, rate limiting |
| Auth | 3001 | Authentication, authorization, JWT management |
| Users | 3002 | User profiles, preferences, subscriptions |
| Upload | 3003 | Video upload, chunk handling, storage orchestration |
| Transcode | 3004 | Video transcoding, format conversion, quality variants |
| Catalog | 3005 | Video metadata, search, categorization |
| Streaming | 3006 | Video delivery, adaptive bitrate, CDN integration |
| Recommendations | 3007 | Content recommendations, watch history, ML inference |
| Billing | 3008 | Payment processing, subscription management, invoicing |
| Analytics | 3009 | View tracking, metrics aggregation, reporting |

## Infrastructure

- **RabbitMQ 3.12**: Message broker for inter-service communication
- **PostgreSQL 15**: Two databases (primary + analytics)
- **Redis 7**: Caching, session storage, rate limiting
- **MinIO**: S3-compatible object storage for video files
- **Consul 1.16**: Service discovery and configuration management

## Bug Categories

The issues span multiple categories typical of distributed Node.js systems:

- **Setup/Configuration** (8): RabbitMQ connections, service discovery, circular dependencies
- **Async/Await** (10): Missing await, promise chains, error handling, race conditions
- **Event Sourcing** (8): Event ordering, idempotency, projection consistency, replay logic
- **Service Communication** (7): Circuit breakers, retry logic, timeout handling, message routing
- **Database/Transactions** (10): Connection pooling, transaction isolation, N+1 queries, migration issues
- **Authentication Chain** (6): JWT propagation, token refresh, OAuth flows, session management
- **Streaming Logic** (8): Chunk handling, bitrate adaptation, seek operations, buffer management
- **Billing/Financial** (6): Payment processing, subscription logic, currency precision, refunds
- **Caching** (6): Cache invalidation, stampede prevention, TTL handling, key collisions
- **Security** (8): Injection attacks, SSRF, prototype pollution, input validation
- **Observability** (5): Trace context, metric cardinality, log correlation
- **JS-Specific** (8): Type coercion, prototype issues, closure problems, this binding

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local development)

### Setup

```bash
cd /Users/amit/projects/terminal-bench-envs/js/mediaflow

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
Pass Rate → Reward
≥ 100% → 1.00
≥ 95% → 0.78
≥ 85% → 0.55
≥ 70% → 0.38
≥ 55% → 0.22
≥ 40% → 0.12
≥ 25% → 0.05
< 25% → 0.00
```

**Target**: to achieve 100% test pass rate  for maximum reward of 1.0.

### Test Execution

```bash
# Run full test suite
npx jest --ci

# Run specific service tests
npx jest services/gateway
npx jest services/streaming
```

## Key Challenges

1. **Service Dependencies**: Some bugs require fixes across multiple services
2. **Event Ordering**: Message-driven architecture requires careful ordering and idempotency
3. **Distributed State**: Coordination between services via RabbitMQ and Consul
4. **Async Complexity**: Deep async/await chains with error propagation
5. **Bug Dependencies**: Some bugs block others - strategic fix ordering matters

## Tips

- Start with setup bugs (L-prefixed) to get services running
- Check RabbitMQ management UI at http://localhost:15672 (guest/guest)
- Monitor logs: `docker compose logs -f <service-name>`
- Use Consul UI at http://localhost:8500 for service discovery
- Test incrementally after each fix to avoid breaking working tests

## Architecture Patterns

- **API Gateway**: Single entry point with request routing
- **Event-Driven**: Async communication via RabbitMQ exchanges and queues
- **CQRS**: Separate read/write models for analytics and streaming
- **Circuit Breaker**: Fault tolerance for inter-service calls
- **Saga Pattern**: Distributed transactions with compensation logic

Good luck debugging!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | DVR Support, Billing Precision, Adaptive Bitrate, Watchlist API, Event Schema |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Content Recommender, Video Clip Generator, Content Moderation |

These tasks test different software engineering skills while using the same codebase.
