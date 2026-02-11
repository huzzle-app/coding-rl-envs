# LatticeForge - Greenfield Implementation Tasks

## Overview

These three greenfield tasks require implementing **new modules from scratch** that integrate with the existing LatticeForge service mesh platform. Each task must follow the established architectural patterns found in `services/` and `latticeforge/`. These challenges test full-stack system design and integration capabilities.

## Environment

- **Language**: Python
- **Infrastructure**: PostgreSQL x3, Redis, NATS
- **Difficulty**: Apex-Principal
- **Task Types**: Greenfield Implementation

## Tasks

### Task 1: Service Discovery Registry

Implement a **Service Discovery Registry** that tracks service instances across the mesh, enabling dynamic endpoint resolution, health-aware routing, and graceful instance deregistration.

**Module Location:**
- `services/discovery/__init__.py`
- `services/discovery/service.py`
- `latticeforge/discovery.py`

**Core Interface:**
The implementation must provide:
- `ServiceInstance` dataclass: Represents a single service instance with instance_id, service_name, endpoint, region, zone, weight, metadata, registered_at, and last_heartbeat
- `HealthStatus` dataclass: Health check result with instance_id, healthy flag, latency_ms, consecutive_failures, last_check, and optional reason
- `ServiceRegistry` class with methods:
  - `register(instance)` - Register a new service instance
  - `deregister(instance_id)` - Remove an instance from the registry
  - `heartbeat(instance_id)` - Update the last heartbeat timestamp
  - `update_health(status)` - Record a health check result
  - `resolve(service_name, region, healthy_only, min_weight)` - Resolve service name to instances
  - `select_instance(service_name, region, strategy)` - Select a single instance using weighted-random, round-robin, or least-connections
  - `stale_instances()` - Return instances that haven't sent a heartbeat within timeout
  - `service_topology()` - Return topology map of services by region

**Service Functions:**
- `create_registry(config)` - Factory function to create a configured ServiceRegistry
- `bulk_register(registry, instances, fail_fast)` - Register multiple instances in batch
- `health_check_sweep(registry, health_results, evict_threshold)` - Process health check results and evict unhealthy instances
- `failover_candidates(registry, service_name, exclude_regions)` - Find failover candidates in non-excluded regions

**Acceptance Criteria:**
- Unit tests with 50+ test cases covering registration, deregistration, heartbeat timeout, health status updates, and each selection strategy
- Integration tests with 20+ test cases testing interaction with gateway for endpoint resolution and resilience for failover
- Minimum 90% line coverage
- Add to `shared/contracts/contracts.py`: `SERVICE_SLO["discovery"] = {"latency_ms": 15, "availability": 0.9999}`

### Task 2: Traffic Mirroring Service

Implement a **Traffic Mirroring Service** that duplicates production traffic to shadow environments for testing, validation, and debugging without impacting production responses.

**Module Location:**
- `services/mirror/__init__.py`
- `services/mirror/service.py`
- `latticeforge/mirror.py`

**Core Interface:**
The implementation must provide:
- `MirrorMode` enum: FULL (mirror all traffic), SAMPLED (sample by percentage), FILTERED (mirror only matching traffic), REPLAY (replay captured traffic)
- `MirrorConfig` dataclass: Configuration for a traffic mirror with mirror_id, source_service, shadow_endpoint, mode, sample_rate, include_intents, exclude_intents, timeout_ms, enabled flag, and created_at
- `MirroredRequest` dataclass: A request that has been mirrored with request_id, trace_id, source_service, intent, payload, headers, and mirrored_at
- `MirrorResult` dataclass: Result of processing a mirrored request with request_id, shadow_endpoint, success flag, latency_ms, response_code, diff_detected, and diff_summary
- `TrafficMirror` class with methods:
  - `add_mirror(config)` - Add a new mirror configuration
  - `remove_mirror(mirror_id)` - Remove a mirror configuration
  - `enable_mirror(mirror_id)` - Enable a disabled mirror
  - `disable_mirror(mirror_id)` - Disable a mirror without removing it
  - `should_mirror(config, intent, sample_seed)` - Determine if a request should be mirrored based on config
  - `capture(request_id, trace_id, source_service, intent, payload, headers)` - Capture a request for mirroring to applicable shadows
  - `pending_count(mirror_id)` - Get count of pending mirrored requests
  - `drain(mirror_id, limit)` - Drain pending requests from a mirror's buffer
  - `stats()` - Get statistics for all mirrors
- `compare_responses(production, shadow, ignore_fields)` - Compare production and shadow responses for differences

**Service Functions:**
- `create_mirror_from_spec(spec)` - Create a MirrorConfig from a specification dict
- `dispatch_to_shadow(request, shadow_endpoint, timeout_ms, shadow_handler)` - Dispatch a mirrored request to shadow environment
- `batch_dispatch(mirror, mirror_id, shadow_handler, batch_size)` - Dispatch a batch of pending mirrored requests
- `analyze_diffs(results, threshold)` - Analyze diff patterns across mirror results

**Acceptance Criteria:**
- Unit tests with 60+ test cases covering all mirror modes, buffer overflow handling, enable/disable lifecycle, and comparison logic with edge cases
- Integration tests with 25+ test cases testing integration with gateway for request capture and audit for mirror event logging
- Minimum 90% line coverage
- Add to `shared/contracts/contracts.py`: `SERVICE_SLO["mirror"] = {"latency_ms": 5, "availability": 0.999}`

### Task 3: Distributed Tracing Collector

Implement a **Distributed Tracing Collector** that aggregates spans from across the service mesh, builds trace trees, computes latency breakdowns, and identifies anomalous traces.

**Module Location:**
- `services/tracing/__init__.py`
- `services/tracing/service.py`
- `latticeforge/tracing.py`

**Core Interface:**
The implementation must provide:
- `SpanKind` enum: SERVER, CLIENT, PRODUCER, CONSUMER, INTERNAL
- `SpanStatus` enum: OK, ERROR, TIMEOUT, CANCELLED
- `Span` dataclass: A single span in a distributed trace with span_id, trace_id, parent_span_id, service_name, operation_name, kind, status, start_time, end_time, tags, and logs; includes `duration_ms` property
- `TraceTree` dataclass: A complete trace assembled from spans with trace_id, root_span, spans tuple, total_duration_ms, service_count, error_count, and assembled_at
- `LatencyBreakdown` dataclass: Latency contribution by service with service_name, total_ms, self_ms (time excluding children), span_count, and error_rate
- `TraceCollector` class with methods:
  - `ingest(span)` - Ingest a span into the collector
  - `ingest_batch(spans)` - Ingest multiple spans
  - `assemble(trace_id)` - Assemble a complete trace from collected spans
  - `get_span(trace_id, span_id)` - Retrieve a specific span
  - `children(trace_id, parent_span_id)` - Get child spans of a given parent
  - `latency_breakdown(trace_id)` - Compute latency breakdown by service for a trace
  - `critical_path(trace_id)` - Identify the critical path (longest sequential chain) in a trace
  - `anomalous_traces(limit)` - Return traces exceeding the anomaly threshold
  - `service_latency_percentiles(service_name, percentiles)` - Compute latency percentiles for a service
  - `incomplete_traces()` - Return trace IDs that have spans but no root span
  - `prune_expired()` - Remove traces older than TTL
- `span_from_dict(data)` - Create a Span from a dictionary payload
- `trace_to_flamegraph(trace)` - Convert a trace tree to flamegraph-compatible format

**Service Functions:**
- `create_collector(config)` - Factory function to create a configured TraceCollector
- `inject_trace_context(headers, trace_id, span_id, sampled)` - Inject trace context into request headers (W3C Trace Context format)
- `extract_trace_context(headers)` - Extract trace context from request headers
- `slo_compliance_report(collector, slo_by_service)` - Generate SLO compliance report from collected traces
- `dependency_graph(collector)` - Build service dependency graph from traces
- `slow_span_analysis(collector, threshold_ms, limit)` - Find and analyze spans exceeding latency threshold

**Acceptance Criteria:**
- Unit tests with 80+ test cases covering span ingestion and deduplication, trace assembly with complex parent-child relationships, critical path detection, percentile computation accuracy, and TTL expiration
- Integration tests with 30+ test cases testing with gateway for context propagation, analytics for SLO compliance, and audit for trace export
- Minimum 90% line coverage
- Add to `shared/contracts/contracts.py`: `SERVICE_SLO["tracing"] = {"latency_ms": 25, "availability": 0.999}` and `REQUIRED_SPAN_FIELDS = {"span_id", "trace_id", "service_name", "operation_name", "start_time", "end_time", "status"}`

## Code Style Requirements

- Follow existing patterns in `latticeforge/` and `services/`
- Use `from __future__ import annotations` in all new files
- Full type hints on all public functions and methods
- Docstrings for all public classes, methods, and functions
- Use `@dataclass(frozen=True)` for immutable value objects

## Testing Standards

- Tests go in `tests/unit/` and `tests/integration/`
- Test file naming: `<module>_test.py`
- Use `unittest` framework consistent with existing tests
- Include edge cases: empty inputs, boundary values, error conditions
- Minimum coverage: 90% line coverage for all new modules

## Success Criteria

Complete implementation meets all acceptance criteria for the chosen task. Deliver working code that:
- Follows LatticeForge architectural patterns
- Has comprehensive unit and integration test coverage
- Achieves 90%+ code coverage
- Integrates seamlessly with existing services
- Updates shared contracts as specified
