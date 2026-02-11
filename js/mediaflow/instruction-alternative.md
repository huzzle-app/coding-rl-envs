# MediaFlow - Alternative Tasks

## Overview

MediaFlow supports five alternative task types that test different software engineering skills beyond debugging: implementing live streaming DVR functionality, refactoring billing precision layers, optimizing transcoding pipelines, extending user-facing APIs, and evolving the event store schema. Each task leverages the existing 10-microservice architecture while addressing real platform challenges.

## Environment

- **Language**: JavaScript (Node.js)
- **Infrastructure**: RabbitMQ, PostgreSQL, Redis, MinIO, Consul
- **Difficulty**: Principal (8-16 hours)

## Tasks

### Task 1: Feature Development - Live Streaming DVR Support

Implement DVR (Digital Video Recording) functionality that allows viewers to pause, rewind, and seek within a live stream's buffer window (30 minutes for free users, 2 hours for premium users). This requires integrating with the existing HLS manifest generation, streaming router, and CDN caching layers while maintaining on-demand video playback.

**Key requirements**: Configurable time-shift buffer per tier, EXT-X-PROGRAM-DATE-TIME tags for timeline sync, seamless buffer segment cleanup, distinct analytics events for time-shifted viewing, and graceful degradation when buffer exhausted.

### Task 2: Refactoring - Unified Billing Precision Layer

Refactor scattered currency precision handling across SubscriptionManager, InvoiceGenerator, and PaymentProcessor into a centralized Money value object pattern. The current implementation suffers from ad-hoc Math.round/floor operations causing penny discrepancies in proration calculations and accounting reconciliation.

**Key requirements**: Consistent precision model (cents or Decimal.js), matching proration results, no floating-point arithmetic on currency, identical API responses for valid inputs, proper rounding, and exact invoice line item totals.

### Task 3: Performance Optimization - Adaptive Bitrate Ladder Generation

Optimize the BitrateCalculator to implement per-title encoding that analyzes source content complexity and generates custom bitrate ladders. A fast complexity analysis pass determines motion characteristics and scene cut frequency to adjust encoding accordingly, reducing storage costs 30-40% while improving perceived quality.

**Key requirements**: Complexity analysis <5% of encode time, high-motion content receives higher bitrate allocation, low-motion content saved 25%+ storage, logged metrics for analysis, graceful fallback to default ladder on timeout, respect min/max configuration bounds.

### Task 4: API Extension - Watchlist and Continue Watching

Extend the platform with user-facing Watchlist and Continue Watching APIs that integrate with existing user, catalog, and analytics services. Users can save videos to watch later, organize with folders, track progress through series, and resume from last watched position with second-level precision.

**Key requirements**: Instant add/remove with eventual consistency, addition timestamp for sorting, debounced playback position persistence, exclude completed videos (>95% watched), auto-remove unpublished content within 5 minutes, cross-device sync via event sourcing, cursor-based pagination, proper cache headers.

### Task 5: Migration - Event Store Schema Evolution

Migrate from simple JSON blob storage to a properly versioned event schema with explicit event type contracts and efficient indexing. Current schema has organic evolution causing 30-minute replay times, no formal versioning, and inconsistent field naming across event types.

**Key requirements**: All existing events queryable/replayable after migration, replay time reduced 50%+, explicit version field and schema documentation per event type, upcasters transforming v1 to current schema, required fields (version, correlationId, causationId), event queries <10ms, rollback within 1 hour.

## Getting Started

```bash
cd /Users/amit/projects/terminal-bench-envs/js/mediaflow
docker compose up -d
npm test
```

## Success Criteria

Implementation meets the acceptance criteria and test requirements defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md). Each task includes specific test commands and integration expectations with the existing codebase.
