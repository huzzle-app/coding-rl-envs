# Scenario 4: Resource Scheduling and Multi-Tenancy Issues

## PagerDuty Incident

**Incident ID**: PD-98234
**Severity**: SEV-2
**Service**: compute-scheduler
**Status**: Investigating

---

## Alert Details

```
[CRITICAL] ComputeOvercommit
  Node: compute-node-17
  Total CPU: 64.0 cores
  Allocated CPU: 64.00000000001 cores  <-- OVER CAPACITY
  Description: Node is overcommitted due to floating-point accumulation errors

[WARNING] PlacementGroupCapacityExceeded
  Placement Group: pg-high-mem-zone
  Max Instances: 10
  Current Instances: 11
  Description: Placement group has more instances than configured limit

[CRITICAL] AntiAffinityViolation
  Workload A: web-frontend-1
  Workload B: web-frontend-2
  Node: compute-node-09
  Description: Both workloads scheduled on same node despite anti-affinity rule

[WARNING] ResourceReservationLeak
  Expired Reservations: 47
  Unreleased CPU: 188 cores
  Unreleased Memory: 752 GB
  Description: Expired reservations are not releasing resources back to nodes
```

---

## Jira Tickets

### CLOUD-4521: Multi-tenant resource isolation bypass

**Reporter**: Security Team
**Priority**: High

During our quarterly security review, we discovered that resources can be created without specifying a tenant ID. The system accepts empty or null tenant_id values, which means resources are not properly scoped to a tenant.

**Reproduction Steps**:
1. Call `POST /api/v1/resources` with `tenant_id: ""`
2. Resource is created successfully
3. Resource is visible to all tenants (no isolation)

**Expected**: API should reject requests with empty/null tenant_id
**Actual**: Request succeeds, creating an orphaned resource

---

### CLOUD-4589: Quota enforcement race condition

**Reporter**: Platform Team
**Priority**: Medium

When two requests to create resources for the same tenant arrive simultaneously, both can succeed even if the total would exceed the tenant's quota.

```
Tenant quota: 10 instances
Current usage: 9 instances
Request A: Create 1 instance -> Allowed (9 < 10)
Request B: Create 1 instance -> Allowed (9 < 10)  # Race!
Final usage: 11 instances  # Exceeds quota!
```

The quota check reads current usage, compares to limit, then increments. There's no atomic read-check-increment operation.

---

### CLOUD-4612: Cross-tenant cache pollution

**Reporter**: Customer Success
**Priority**: High

Customer A is seeing resource data from Customer B in their dashboard. Investigation shows the cache key doesn't include tenant_id:

```python
# Current implementation
cache_key = f"resource:{resource_id}"

# Should be
cache_key = f"{tenant_id}:resource:{resource_id}"
```

This means Tenant A's cache lookup can return Tenant B's cached data if they have resources with the same ID format.

---

### CLOUD-4634: Tenant deletion leaves orphaned resources

**Reporter**: Operations
**Priority**: Medium

When a tenant is deleted, their resources in compute, network, and storage services are not cleaned up. The tenant deletion only removes the tenant record from the tenants database but doesn't cascade to dependent services.

**Impact**: Orphaned resources consuming capacity, billing records with no associated tenant.

---

### CLOUD-4678: Billing isolation failure

**Reporter**: Finance
**Priority**: High

Usage metering for shared infrastructure costs is using float division, which loses precision and causes billing allocations across tenants to not sum to the total cost.

Example from this month:
```
Shared cost: $10,000.00
Tenant A (30%): $2,999.99
Tenant B (30%): $2,999.99
Tenant C (40%): $3,999.99
Total allocated: $9,999.97 (missing $0.03)
```

---

## Compute Scheduler Logs

```
2024-01-15T14:23:01.234Z scheduler [DEBUG] Scheduling workload wl-abc123 (cpu=8.1, mem=32)
2024-01-15T14:23:01.234Z scheduler [DEBUG] Node compute-node-17 available: cpu=8.100000000000001, mem=128
2024-01-15T14:23:01.235Z scheduler [DEBUG] Capacity check: 8.1 <= 8.100000000000001 = True
2024-01-15T14:23:01.235Z scheduler [INFO] Workload wl-abc123 scheduled on compute-node-17
2024-01-15T14:23:01.236Z scheduler [WARNING] Node compute-node-17 now shows available_cpu=-0.000000000000001

2024-01-15T14:23:05.891Z scheduler [DEBUG] Evaluating anti-affinity for workload wl-def456
2024-01-15T14:23:05.891Z scheduler [DEBUG] Checking node compute-node-09: existing workloads [wl-xyz789]
2024-01-15T14:23:05.892Z scheduler [DEBUG] Concurrent scheduling detected - both wl-def456 and wl-ghi012 checking same node
2024-01-15T14:23:05.893Z scheduler [WARNING] Anti-affinity violation: wl-def456 and wl-ghi012 both placed on compute-node-09

2024-01-15T14:30:00.001Z scheduler [INFO] Cleaning expired reservations...
2024-01-15T14:30:00.045Z scheduler [INFO] Removed 23 expired reservations
2024-01-15T14:30:00.046Z scheduler [WARNING] Node capacity unchanged after cleanup (resources not released)
```

---

## Affected Components

- `services/compute/main.py` - Scheduler, bin packing, affinity rules
- `services/tenants/models.py` - Tenant scoping, quota enforcement, cache
- `shared/utils/distributed.py` - Resource locking

---

## Test Failures Related

```
FAILED tests/unit/test_resource_scheduling.py::TestScheduler::test_no_overcommit_float_precision
FAILED tests/unit/test_resource_scheduling.py::TestScheduler::test_placement_group_capacity_limit
FAILED tests/unit/test_resource_scheduling.py::TestScheduler::test_anti_affinity_atomic
FAILED tests/unit/test_resource_scheduling.py::TestScheduler::test_affinity_before_anti_affinity
FAILED tests/unit/test_resource_scheduling.py::TestScheduler::test_drain_flag_respected
FAILED tests/unit/test_resource_scheduling.py::TestScheduler::test_reservation_cleanup_releases_resources
FAILED tests/unit/test_multi_tenancy.py::TestMultiTenancy::test_tenant_id_required
FAILED tests/unit/test_multi_tenancy.py::TestMultiTenancy::test_quota_enforcement_atomic
FAILED tests/unit/test_multi_tenancy.py::TestMultiTenancy::test_cache_isolation_by_tenant
FAILED tests/unit/test_multi_tenancy.py::TestMultiTenancy::test_tenant_deletion_cascades
FAILED tests/unit/test_multi_tenancy.py::TestMultiTenancy::test_billing_isolation_precision
```

---

## Impact Summary

| Issue | Frequency | Business Impact |
|-------|-----------|-----------------|
| Float precision overcommit | ~5% of scheduling decisions | Degraded performance on affected nodes |
| Placement group overflow | ~2% of placements | HA guarantees violated |
| Anti-affinity race | ~1% under load | Service co-location risks |
| Reservation leak | Daily | 10-15% wasted capacity |
| Tenant isolation | Continuous | Security/compliance violation |
