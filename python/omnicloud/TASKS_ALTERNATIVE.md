# OmniCloud - Alternative Task Specifications

This document contains alternative task specifications for the OmniCloud multi-cloud infrastructure orchestration platform. Each task represents a realistic engineering challenge that cloud platform teams encounter.

---

## Task 1: Multi-Region Failover Automation (Feature Development)

### Description

OmniCloud currently lacks automated failover capabilities when a primary region experiences an outage. Customers have requested the ability to configure automatic failover policies that trigger when health checks fail across multiple availability zones. The system should detect regional failures, automatically promote standby resources in secondary regions, and update DNS records to redirect traffic.

The failover system must handle complex dependency chains between resources (e.g., a web tier depends on an application tier, which depends on a database tier). Resources must failover in the correct order to maintain data consistency and avoid cascading failures. The system should also support configurable failover thresholds to prevent flapping during transient network issues.

Additionally, the failover mechanism needs to integrate with the existing billing service to properly attribute costs to the correct region and tenant during and after failover events, ensuring accurate invoicing even when resources are running in multiple regions simultaneously.

### Acceptance Criteria

- Failover policies can be configured per tenant with customizable health check thresholds and evaluation windows
- Dependency-aware failover executes in topological order (databases before application servers, application servers before load balancers)
- DNS records are automatically updated within 60 seconds of failover initiation using the existing DNS service
- Failover events are recorded in the audit trail with timestamps, affected resources, and triggering conditions
- Billing correctly tracks resource usage in both primary and secondary regions during failover periods
- Manual failover override is available for emergency situations
- Failback to primary region is supported once health checks pass for a configurable duration
- Integration tests verify failover completes successfully under simulated regional outage conditions

### Test Command

```bash
python -m pytest tests/integration/test_failover_automation.py -v
```

---

## Task 2: Infrastructure State Reconciliation Refactoring (Refactoring)

### Description

The current infrastructure state management system in the shared/infra module has grown organically and now contains significant technical debt. The StateManager class handles resource lifecycle, drift detection, snapshots, and dependency graph operations all in a single monolithic class. This has led to testing difficulties, unclear responsibility boundaries, and challenges when multiple engineers work on state-related features simultaneously.

The reconciliation logic is tightly coupled with the state storage layer, making it impossible to swap backends or implement caching without significant changes. The dependency graph building and cycle detection are intermingled with resource CRUD operations, and the snapshot mechanism lacks proper isolation from live state mutations.

Refactor the state management system into cohesive, single-responsibility components: a StateMachine for resource lifecycle transitions, a DriftDetector for comparing desired vs actual state, a DependencyResolver for graph operations, and a SnapshotManager for state persistence. Each component should be independently testable and support dependency injection for external services.

### Acceptance Criteria

- StateMachine class handles only resource state transitions with clear valid/invalid transition rules
- DriftDetector class provides pluggable comparison strategies (exact match, semantic equality, threshold-based)
- DependencyResolver class performs topological sorting, cycle detection, and dependency impact analysis
- SnapshotManager class handles serialization, compression, and atomic snapshot operations
- All existing unit tests continue to pass after refactoring
- New unit tests achieve 90% coverage for each extracted component
- Integration tests verify the components work together correctly
- No changes to the public API consumed by other services (backward compatibility)

### Test Command

```bash
python -m pytest tests/unit/test_infrastructure_state.py tests/integration/test_service_communication.py -v
```

---

## Task 3: Resource Scheduling Performance Optimization (Performance Optimization)

### Description

Performance profiling has revealed that the compute scheduler becomes a bottleneck as the number of nodes and active workloads increases. The current bin-packing algorithm iterates through all nodes for every scheduling decision, and the affinity/anti-affinity rule evaluation performs redundant calculations. Customers with 500+ nodes are experiencing scheduling latencies exceeding 2 seconds, which is unacceptable for burst workload scenarios.

The scheduler also rebuilds the placement group membership data on every scheduling call rather than maintaining an incrementally updated index. Anti-affinity checks perform O(n*m) comparisons where n is candidate nodes and m is anti-affinity rules, when a pre-computed index could reduce this to O(n) lookups.

Optimize the scheduler to handle 1000+ nodes with scheduling latency under 100ms for 95th percentile requests. The optimization should maintain scheduling quality (avoid over-commit, respect all constraints) while dramatically improving throughput. Consider implementing node indexing by region and resource availability, caching placement group membership, and pre-filtering candidates based on resource requirements.

### Acceptance Criteria

- Scheduling latency p95 is under 100ms with 1000 nodes and 50 concurrent scheduling requests
- Scheduling latency p99 is under 250ms under the same conditions
- Memory usage does not exceed 2x the current baseline when indexing structures are populated
- All existing scheduling correctness tests pass (no over-commit, constraints respected)
- Benchmark tests demonstrate at least 10x throughput improvement for large cluster scenarios
- Index structures are properly invalidated when nodes are added, removed, or updated
- Performance regression tests are added to the CI pipeline
- Documentation explains the new indexing strategy and any operational considerations

### Test Command

```bash
python -m pytest tests/performance/test_provisioning.py tests/unit/test_resource_scheduling.py -v
```

---

## Task 4: Deployment Webhook API Extension (API Extension)

### Description

The deployment service currently only supports polling for deployment status. DevOps teams have requested webhook integration to receive real-time notifications when deployments transition between states (queued, in_progress, completed, failed, rolled_back). This enables integration with external CI/CD systems, Slack notifications, and custom monitoring dashboards without constant polling overhead.

Webhooks should support configurable event filtering (e.g., only notify on failures), payload customization templates, and retry logic with exponential backoff for failed deliveries. Each tenant should be able to register multiple webhook endpoints with different event subscriptions. Webhook payloads must include deployment metadata, timing information, and links to relevant logs.

The webhook system must handle high-volume deployment scenarios where hundreds of deployments complete within minutes during automated rollouts. Failed webhook deliveries should be logged for debugging and retried according to the configured policy without blocking deployment progression.

### Acceptance Criteria

- Tenants can register, update, and delete webhook endpoints via REST API
- Webhook subscriptions support filtering by event type (state_change, health_check_failed, rollback_initiated)
- Webhook payloads include deployment_id, tenant_id, service_name, old_state, new_state, timestamp, and duration
- Payload templates support Jinja2-style variable substitution for custom formatting
- Failed deliveries retry with exponential backoff (1s, 2s, 4s, 8s, max 5 attempts)
- Webhook delivery status is queryable via API (pending, delivered, failed, exhausted)
- Rate limiting prevents webhook storms from overwhelming recipient systems (max 100/minute per endpoint)
- Contract tests verify webhook payload schemas match documented specifications

### Test Command

```bash
python -m pytest tests/contract/test_api_contracts.py tests/integration/test_deployment_pipeline.py -v
```

---

## Task 5: Billing System Currency Migration (Migration)

### Description

OmniCloud's billing service currently stores all monetary values as USD with implicit conversion at display time. To properly support international customers and comply with EU invoicing regulations, the billing system must migrate to store amounts in the tenant's configured billing currency with explicit exchange rate tracking. This affects invoice generation, cost allocation, credit application, and usage metering.

The migration must be backward compatible - existing invoices should remain queryable with their original USD amounts, while new invoices are generated in the tenant's billing currency. Historical exchange rates must be preserved for audit purposes, and the system should handle exchange rate fluctuations during billing period boundaries.

The migration involves updating the billing data model, implementing currency conversion utilities with precision handling (different currencies have different decimal places), modifying the proration and discount calculation logic to be currency-aware, and adding migration scripts that backfill currency information for existing tenants without disrupting ongoing billing cycles.

### Acceptance Criteria

- Tenant model includes billing_currency field with ISO 4217 currency codes (USD, EUR, GBP, JPY, etc.)
- All monetary calculations use currency-appropriate decimal precision (2 decimals for USD/EUR, 0 for JPY)
- Invoice generation stores amount, currency, and exchange_rate_to_usd at time of generation
- Historical invoices remain unchanged and queryable in their original currency
- Cost allocation correctly handles multi-currency tenant pools
- Discount and credit application respects currency of the original charge
- Migration script processes existing tenants in batches with progress checkpointing
- Billing isolation tests verify no cross-currency contamination between tenants

### Test Command

```bash
python -m pytest tests/unit/test_billing_metering.py tests/chaos/test_multi_tenancy.py -v
```
