# OmniCloud - Greenfield Tasks

## Overview

These 3 greenfield implementation tasks require building complete new services and modules from scratch following OmniCloud architectural patterns. Each task involves implementing data models, service logic, REST endpoints, and comprehensive tests while integrating with existing platform services.

## Environment

- **Language**: Python
- **Infrastructure**: Kafka, PostgreSQL x4, Redis, Consul, etcd, HashiCorp Vault, MinIO
- **Difficulty**: Distinguished Engineer (24-48 hours)
- **Microservices**: 15 (Gateway, Auth, Tenants, Compute, Network, Storage, DNS, LoadBalancer, Secrets, Config, Deploy, Monitor, Billing, Audit, Compliance)

## Tasks

### Task 1: Cost Allocation Service (Type: New Service)

Build a **Cost Allocation Service** that tracks and attributes cloud costs to tenants, projects, and resources using multi-dimensional cost attribution. The service handles shared infrastructure cost allocation (control plane, monitoring, logging), reserved capacity amortization, and tag-based cost grouping with support for custom allocation rules (e.g., 70% of shared costs by compute usage, 30% by storage).

**Interface Contract**:
- **AllocationRule**: Defines cost allocation strategy (proportional, equal, tiered, custom) with effective period and weight-by-category configuration
- **CostAllocationResult**: Result with tenant costs, period bounds, and category breakdown using Decimal precision
- **CostAllocationService** methods: `calculate_tenant_allocation()`, `allocate_shared_costs()`, `calculate_amortized_reserved_costs()`, `get_cost_by_tags()`, `detect_cost_anomalies()`, `create_allocation_rule()`, `get_historical_costs()`
- **Enums**: AllocationStrategy (proportional, equal, tiered, custom), CostCategory (compute, storage, network, shared, reserved, support)

**Key Requirements**:
- Zero rounding loss: sum of allocations must equal shared_cost
- Edge case handling: new tenant with zero usage, mid-period deletions, resource owner changes
- Decimal precision for all monetary calculations
- Integration with billing service for usage data
- Cost anomaly detection using statistical thresholds (>2 std dev from mean)
- ServiceClient pattern for billing service integration
- 60+ unit tests covering edge cases
- Integration tests with billing service

**Test Command**: `python -m pytest tests/unit/test_cost_allocation.py tests/integration/test_cost_allocation_billing.py -v`

### Task 2: Infrastructure Drift Detector (Type: New Module in shared/infra/)

Implement an **Infrastructure Drift Detector** module that detects configuration drift between desired state (infrastructure-as-code) and actual state (observed from providers). Unlike naive dict comparison, this detector handles semantic equivalence (string "8080" == int 8080), unordered collections (security group rules), and nested object comparison with categorized severity levels.

**Interface Contract**:
- **DriftRecord**: Individual drift with resource_id, config_path (e.g., "security_groups[0].rules[2].port"), desired_value, actual_value, and severity classification
- **DriftReport**: Aggregated report for tenant/resource scan with summary counts by severity
- **DriftDetector** methods: `detect_resource_drift()`, `scan_tenant_resources()`, `classify_drift_severity()`, `generate_remediation_plan()`, `register_comparator()`, `mark_field_unordered()`, `add_severity_rule()`, `get_drift_history()`
- **Enums**: DriftSeverity (cosmetic, functional, security, critical), DriftType (value_changed, key_added, key_removed, type_mismatch, resource_missing, resource_extra)

**Key Requirements**:
- Semantic comparison: type coercion (string/int ports, bool "true"/True)
- Unordered field handling: security group rules compared as sets
- Full nested path reporting (e.g., "network.subnets[0].cidr")
- None vs missing key treated as distinct drift types
- Configurable severity classification rules
- Remediation plan generation with approval requirements for security changes
- Security-impacting drifts (ingress 0.0.0.0/0) classified as CRITICAL
- Drift history persisted for audit trail
- 80+ unit tests covering comparison edge cases
- Integration tests with StateManager and reconciler

**Test Command**: `python -m pytest tests/unit/test_drift_detector.py tests/integration/test_drift_reconciler.py -v`

### Task 3: Capacity Forecasting Engine (Type: New Service)

Build a **Capacity Forecasting Engine** that predicts future resource needs using time-series analysis with support for multiple forecasting scenarios (organic growth, seasonal patterns, what-if analysis). The engine forecasts compute, storage, and network capacity requirements with configurable confidence intervals and detects regime changes (pattern shifts post-migration).

**Interface Contract**:
- **UsageDataPoint**: Single measurement with timestamp, value, and optional metadata
- **ForecastResult**: Predictions with P10/P50/P90 confidence intervals, model metadata, seasonality detection, and confidence score
- **CapacityRecommendation**: Actionable recommendation with current/recommended capacity, confidence, projected exhaustion date, and cost delta
- **CapacityForecastEngine** methods: `forecast_metric()`, `detect_seasonality()`, `detect_regime_change()`, `generate_capacity_recommendations()`, `project_capacity_exhaustion()`, `run_what_if_scenario()`, `estimate_reserved_capacity_savings()`, `get_historical_accuracy()`, `train_custom_model()`
- **Enums**: ResourceMetric (cpu_utilization, memory_utilization, storage_used_gb, network_bandwidth_mbps, instance_count, request_rate), ForecastGranularity (hourly, daily, weekly, monthly), SeasonalityType (none, daily, weekly, monthly, yearly)

**Key Requirements**:
- Minimum 14 days historical data requirement (error if insufficient)
- Seasonality detection using autocorrelation at multiple intervals
- Regime change detection identifying distribution shifts
- Confidence intervals widen appropriately for longer horizons
- Capacity exhaustion projection using P90 forecast (conservative)
- What-if scenario support: traffic_multiplier, new_workload addition, workload removal
- Reserved capacity recommendations with break-even utilization analysis
- Historical accuracy tracking (MAPE, RMSE, bias metrics)
- Cost estimates with Decimal precision
- 70+ unit tests covering models and edge cases
- Integration tests with compute scheduler and billing service

**Test Command**: `python -m pytest tests/unit/test_capacity_forecast.py tests/integration/test_capacity_compute.py -v`

## Implementation Guidelines

### Service Structure
Each new service should follow OmniCloud patterns:
- `services/<service_name>/models.py` - Data classes with `@dataclass` decorator
- `services/<service_name>/views.py` or `main.py` - FastAPI endpoints if API exposed
- `services/<service_name>/settings.py` - Service configuration
- `services/<service_name>/__init__.py` - Package initialization

### Shared Module Structure
Modules in `shared/infra/` follow:
- Single responsibility classes with `@dataclass`
- Type hints on all methods
- Comprehensive docstrings

### Inter-Service Communication
Use `ServiceClient` from `shared/clients/base.py`:
- Circuit breaker pattern for resilience
- Correlation ID propagation for tracing
- Tenant ID in headers for multi-tenancy

### Monetary Calculations
Always use `Decimal` from Python's decimal module:
- Never use `float` for money
- Explicit rounding with `quantize()`

### Time Handling
Use timezone-aware datetimes:
- `datetime.now(timezone.utc)` not `datetime.now()`
- Store timestamps as floats (Unix epoch) for consistency

## Getting Started

```bash
# Start all services
docker compose up -d

# Run tests for greenfield tasks
python -m pytest tests/unit/test_cost_allocation.py -v                    # Task 1
python -m pytest tests/unit/test_drift_detector.py -v                     # Task 2
python -m pytest tests/unit/test_capacity_forecast.py -v                  # Task 3
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).

Each greenfield task includes:
- Complete service implementation with all required methods
- Data models matching specified interface contracts
- REST API endpoints (if service is consumer-facing)
- Integration tests demonstrating cross-service communication
- Comprehensive unit tests (60-70+ tests per service)
- Full adherence to architectural patterns
- No external dependencies beyond platform services
