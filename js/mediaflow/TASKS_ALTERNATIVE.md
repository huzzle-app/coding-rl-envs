# MediaFlow - Alternative Task Specifications

This document contains alternative task specifications for the MediaFlow video streaming platform. Each task provides a different challenge type while leveraging the existing codebase architecture.

---

## Task 1: Feature Development - Live Streaming DVR Support

### Description

MediaFlow currently supports basic live streaming through the HLS service, but lacks true DVR (Digital Video Recording) functionality that allows viewers to pause, rewind, and seek within a live stream's buffer window. Users are requesting the ability to jump back up to 2 hours during live events like concerts, sports, and premieres.

Implement DVR support for live streams including a configurable time-shift buffer, seamless transition between live and time-shifted playback, and proper segment retention management. The implementation must integrate with the existing HLS manifest generation, streaming router, and CDN caching layers without disrupting on-demand video playback.

The DVR feature should maintain segment availability based on subscription tier (free users get 30-minute buffer, premium users get 2-hour buffer), properly handle edge cases like buffer exhaustion and live edge catchup, and emit appropriate analytics events for time-shifted viewing.

### Acceptance Criteria

- DVR buffer window is configurable per-stream and per-subscription tier (30 min free, 2 hours premium)
- Live manifest includes EXT-X-PROGRAM-DATE-TIME tags for DVR timeline synchronization
- Seeking within the DVR window returns appropriate segments without hitting origin for cached content
- Buffer segment cleanup runs automatically to prevent unbounded storage growth
- Time-shift viewing triggers distinct analytics events differentiating live vs DVR playback
- Graceful degradation when DVR buffer is exhausted (snap to live edge)
- All existing live streaming tests continue to pass
- New DVR-specific test cases achieve >90% coverage

### Test Command

```bash
npm test
```

---

## Task 2: Refactoring - Unified Billing Precision Layer

### Description

The billing service currently suffers from scattered currency precision handling across multiple components. The SubscriptionManager, InvoiceGenerator, and PaymentProcessor each implement their own rounding and decimal handling, leading to proration calculation mismatches and occasional penny discrepancies that trigger customer complaints and accounting reconciliation issues.

Refactor the billing domain to centralize all monetary calculations through a unified precision layer. This should eliminate the ad-hoc Math.round, Math.floor, and floating-point division scattered throughout billing code. The refactoring must preserve all existing API contracts and behavior for correctly-handled cases while fixing precision-related bugs.

The goal is to create a Money value object pattern that encapsulates currency operations, enforces immutability, and provides proper banker's rounding. All billing components should delegate monetary math to this centralized abstraction rather than performing raw arithmetic.

### Acceptance Criteria

- All currency amounts are represented using a consistent precision model (cents or Decimal.js)
- Proration calculations between subscription and invoice components produce matching results
- No floating-point arithmetic performed directly on currency values anywhere in billing code
- Existing billing API endpoints return identical responses for valid inputs
- Currency conversion (if applicable) uses proper mid-market rates with configurable spreads
- Invoice line item totals always sum exactly to invoice total (no rounding drift)
- Billing test suite passes with identical expected values (no tolerance epsilon)
- Refactoring introduces no new public API surface to billing service

### Test Command

```bash
npm test
```

---

## Task 3: Performance Optimization - Adaptive Bitrate Ladder Generation

### Description

The transcoding service generates fixed bitrate ladders for all content regardless of source characteristics. A 4K nature documentary with slow panning shots wastes bandwidth encoding at high bitrates, while a fast-action gaming stream suffers quality degradation at those same bitrates. Content-aware encoding could reduce storage costs by 30-40% while improving perceived quality.

Optimize the BitrateCalculator and transcoding pipeline to implement per-title encoding that analyzes source content complexity and generates custom bitrate ladders. The system should perform a fast complexity analysis pass on source video to determine motion characteristics, scene cut frequency, and spatial detail levels, then adjust the bitrate ladder accordingly.

This optimization must work within the existing transcoding worker queue architecture, emit appropriate metrics for encoding efficiency analysis, and gracefully degrade to default ladders if complexity analysis times out or fails.

### Acceptance Criteria

- Complexity analysis runs in <5% of encode time for standard content
- High-motion content (sports, gaming) receives higher bitrate allocation for equivalent quality
- Low-motion content (documentaries, interviews) receives reduced bitrate ladder saving 25%+ storage
- Per-title encoding decisions are logged with complexity metrics for analysis
- Encoding failures gracefully fall back to default ladder without blocking the pipeline
- Bitrate ladder generation respects min/max bounds from service configuration
- HLS manifests reflect actual encoded bitrates (not assumed defaults)
- Transcoding test suite validates ladder customization for sample content types

### Test Command

```bash
npm test
```

---

## Task 4: API Extension - Watchlist and Continue Watching

### Description

MediaFlow lacks personalized content organization features that users expect from modern streaming platforms. Users want to save videos to watch later, track their progress through series, and easily resume partially-watched content. The recommendations service has watch history but this is not exposed as user-facing functionality.

Extend the platform with Watchlist and Continue Watching APIs that integrate with the existing user, catalog, and analytics services. The watchlist should support organization (folders/collections), sync across devices, and respect content availability (remove items when videos are unpublished). Continue Watching should track playback position with second-level precision and surface contextually-aware resume points.

The implementation should leverage existing event sourcing patterns for durability, integrate with the recommendations engine for intelligent ordering, and provide efficient bulk operations for client applications.

### Acceptance Criteria

- Users can add/remove videos to their watchlist with instant consistency
- Watchlist items include addition timestamp for "recently added" sorting
- Playback position is persisted when videos are paused or closed (debounced, not per-second)
- Continue Watching excludes completed videos (>95% watched)
- Unpublished videos are automatically removed from watchlists within 5 minutes
- Cross-device sync maintains eventual consistency via event sourcing
- Bulk fetch operations support pagination with cursor-based navigation
- Client-facing APIs include proper cache headers for CDN efficiency
- New endpoints follow existing API conventions and authentication patterns

### Test Command

```bash
npm test
```

---

## Task 5: Migration - Event Store Schema Evolution

### Description

The event sourcing implementation in MediaFlow uses a simple JSON blob storage pattern that has reached its limits. The schema has evolved organically with each feature addition, resulting in events that cannot be efficiently queried, inconsistent field naming across event types, and no formal versioning strategy. Replaying the event log now takes over 30 minutes.

Migrate the event store to a properly versioned schema with explicit event type contracts, efficient indexing for common query patterns, and built-in support for schema evolution through upcasting. The migration must be performed with zero downtime, maintaining the ability to replay historical events while new events follow the updated schema.

The migration should introduce event versioning (semantic or incrementing), implement upcasters that transform old events to current schema during replay, add appropriate database indexes for event stream queries, and provide tooling for future schema changes.

### Acceptance Criteria

- All existing events remain queryable and replayable after migration
- Event replay time reduced by 50% or more through proper indexing
- Each event type has explicit version field and schema documentation
- Upcasters transform v1 events to current schema transparently
- New events include required fields: version, correlationId, causationId
- Event queries by aggregate ID complete in <10ms for typical streams
- Schema changes can be deployed independently of application code
- Migration can be rolled back within 1 hour if issues discovered
- Event sourcing tests validate both legacy and versioned event formats

### Test Command

```bash
npm test
```

---

## Notes

- All tasks assume familiarity with the MediaFlow service architecture (10 microservices)
- Tasks should be completed without modifying test expectations unless explicitly required
- Integration with existing infrastructure (Redis, RabbitMQ, PostgreSQL, MinIO) is expected
- Observability (metrics, traces, logs) should be maintained or enhanced for new functionality
