# OmniCloud - Alternative Tasks

## Overview

These 5 alternative tasks represent realistic engineering challenges in a multi-cloud platform: automated failover with regional dependencies, refactoring monolithic state management, optimizing resource scheduling, extending deployment APIs, and migrating billing infrastructure to support multiple currencies. Each task tests different software engineering skills while using the same OmniCloud codebase.

## Environment

- **Language**: Python
- **Infrastructure**: Kafka, PostgreSQL x4, Redis, Consul, etcd, HashiCorp Vault, MinIO
- **Difficulty**: Distinguished Engineer (24-48 hours)
- **Microservices**: 15 (Gateway, Auth, Tenants, Compute, Network, Storage, DNS, LoadBalancer, Secrets, Config, Deploy, Monitor, Billing, Audit, Compliance)

## Tasks

### Task 1: Multi-Region Failover Automation (Feature Development)

Implement automated failover capabilities for regional outages with dependency-aware resource promotion, DNS updates within 60 seconds, and proper billing attribution. The system must handle complex resource dependency chains (databases before application servers) and support configurable failover thresholds to prevent flapping during transient issues.

**Key Requirements**: Failover policies per tenant, topological ordering of resource failover, DNS integration, audit logging, billing integration, manual override capability, failback support, and integration tests.

**Test Command**: `python -m pytest tests/integration/test_failover_automation.py -v`

### Task 2: Infrastructure State Reconciliation Refactoring (Refactoring)

Refactor the monolithic StateManager class into cohesive, single-responsibility components: StateMachine for lifecycle transitions, DriftDetector for state comparison, DependencyResolver for graph operations, and SnapshotManager for persistence. Each component must be independently testable with dependency injection support while maintaining full backward compatibility.

**Key Requirements**: Clear responsibility boundaries, pluggable comparison strategies, topological sorting and cycle detection, snapshot isolation, 90% coverage per component, and public API compatibility.

**Test Command**: `python -m pytest tests/unit/test_infrastructure_state.py tests/integration/test_service_communication.py -v`

### Task 3: Resource Scheduling Performance Optimization (Performance Optimization)

Optimize the compute scheduler to handle 1000+ nodes with p95 latency under 100ms and p99 under 250ms. Current bin-packing algorithm becomes a bottleneck; implement node indexing by region/resource availability, cache placement group membership, and pre-filter candidates to reduce affinity rule evaluation from O(n*m) to O(n) lookups.

**Key Requirements**: Scheduling latency targets (p95 <100ms, p99 <250ms), 10x throughput improvement for large clusters, correctness preservation, index invalidation on node changes, benchmark tests, and regression test integration.

**Test Command**: `python -m pytest tests/performance/test_provisioning.py tests/unit/test_resource_scheduling.py -v`

### Task 4: Deployment Webhook API Extension (API Extension)

Add webhook support to the deployment service for real-time status notifications with configurable event filtering, payload customization via Jinja2 templates, and retry logic with exponential backoff. Tenants should register multiple endpoints per subscription, with delivery status tracking and rate limiting (100/minute per endpoint) to prevent overwhelming recipients.

**Key Requirements**: REST API for webhook management, event filtering by type, template-based payload customization, exponential backoff retry (1s, 2s, 4s, 8s, max 5 attempts), delivery status querying, rate limiting, and contract tests.

**Test Command**: `python -m pytest tests/contract/test_api_contracts.py tests/integration/test_deployment_pipeline.py -v`

### Task 5: Billing System Currency Migration (Migration)

Migrate billing system from implicit USD-only storage to explicit multi-currency support with tenant-configured billing currencies, ISO 4217 currency codes, and currency-appropriate decimal precision. Maintain backward compatibility for historical invoices, track exchange rates at generation time, and ensure cost allocation handles multi-currency tenant pools without cross-currency contamination.

**Key Requirements**: Billing_currency field on tenant model, currency-appropriate decimal precision, invoice generation with exchange rate tracking, historical invoice compatibility, currency-aware calculations, migration script with checkpointing, and isolation tests.

**Test Command**: `python -m pytest tests/unit/test_billing_metering.py tests/chaos/test_multi_tenancy.py -v`

## Getting Started

```bash
# Start all services
docker compose up -d

# Run tests for alternative tasks
python -m pytest tests/integration/test_failover_automation.py -v          # Task 1
python -m pytest tests/unit/test_infrastructure_state.py -v               # Task 2
python -m pytest tests/performance/test_provisioning.py -v                # Task 3
python -m pytest tests/contract/test_api_contracts.py -v                  # Task 4
python -m pytest tests/unit/test_billing_metering.py -v                   # Task 5
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).

Each task includes:
- Feature-complete implementation of new capabilities or refactored components
- All specified acceptance criteria satisfied
- Integration tests demonstrating cross-service correctness
- No regression in existing functionality
