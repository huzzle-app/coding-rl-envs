# ALERT: Configuration Override Failure Detected

**Alert ID**: IONVEIL-CFG-7892
**Severity**: Warning (Auto-escalated to Critical after 4h)
**First Triggered**: 2024-03-22 03:17:42 UTC
**Current Status**: FIRING
**Affected Service**: ionveil-config / shared.config

---

## Alert Details

| Field | Value |
|-------|-------|
| Alert Name | `config_env_override_ineffective` |
| Expression | `ionveil_config_env_value != ionveil_config_active_value` |
| Duration | 4h 23m |
| Cluster | prod-east-1 |
| Namespace | ionveil-platform |
| Pods Affected | All 24 gateway replicas |

---

## Alert Description

Environment variable configuration values are not being applied correctly. The system is using values from the YAML configuration file instead of environment variable overrides, breaking the expected configuration precedence:

**Expected Order** (highest to lowest priority):
1. Environment variables
2. Environment-specific YAML overlay
3. Base YAML configuration
4. Built-in defaults

**Observed Behavior**: YAML file values override environment variables (inverted precedence)

---

## Detected Discrepancy

```
=== Configuration Mismatch Report ===

Key: db.port
  Environment Variable (IONVEIL_DB_PORT): 5433
  Active Configuration Value: 5432
  Source: config.yaml

Key: db.pool_max
  Environment Variable (IONVEIL_DB_POOL_MAX): 50
  Active Configuration Value: 10
  Source: config.yaml

Key: redis.host
  Environment Variable (IONVEIL_REDIS_HOST): redis-cluster.prod.svc
  Active Configuration Value: localhost
  Source: default
```

---

## Impact Assessment

### Immediate Issues

1. **Database Connections**: Pods connecting to port 5432 (old primary) instead of 5433 (new primary after maintenance)
2. **Connection Pool Exhaustion**: Pool max of 10 instead of 50 causing request queuing
3. **Redis Failures**: Pods trying to connect to localhost instead of cluster DNS

### Cascading Failures

```
2024-03-22 03:18:01 [gateway-7] ERROR: Connection refused to localhost:6379
2024-03-22 03:18:01 [gateway-7] ERROR: Redis cache unavailable, falling back to DB
2024-03-22 03:18:02 [gateway-7] WARN: Connection pool exhausted (10/10), request queued
2024-03-22 03:18:32 [gateway-7] ERROR: Request timeout after 30s waiting for DB connection
```

### Service Health

| Service | Status | Error Rate |
|---------|--------|------------|
| Gateway | Degraded | 23% 5xx |
| Auth | Degraded | 18% timeout |
| Dispatch | Critical | 41% failure |
| Routing | Healthy | 0.3% error |

---

## Root Cause Investigation

### Configuration Loading Sequence

The `IonVeilConfig._load()` method should apply sources in order:
1. Start with `_DEFAULTS`
2. Merge environment variables (from `_read_env_overrides()`)
3. Merge base YAML file
4. Merge environment-specific overlay

**Problem**: Environment overrides are being applied BEFORE YAML loading, causing YAML to overwrite environment values.

### Test Validation

```python
# From tests/unit/config_test.py
def test_config_env_overrides_file(self):
    os.environ["IONVEIL_DB_PORT"] = "5433"
    config = IonVeilConfig()
    # This assertion fails:
    assert config.get("db.port") == 5433  # Actual: 5432
```

### Failing Tests

```
FAIL: tests/unit/config_test.py::test_config_env_overrides_file
FAIL: tests/unit/config_test.py::test_config_precedence_order
FAIL: tests/integration/startup_test.py::test_env_vars_take_precedence
```

---

## Kubernetes Environment

```yaml
# Deployment environment variables (should take precedence)
env:
  - name: IONVEIL_DB_PORT
    value: "5433"
  - name: IONVEIL_DB_POOL_MAX
    value: "50"
  - name: IONVEIL_REDIS_HOST
    value: "redis-cluster.prod.svc"

# ConfigMap mounted at /etc/ionveil/config.yaml
data:
  config.yaml: |
    db:
      host: db-primary.prod.svc
      port: 5432
      pool_max: 10
    redis:
      host: localhost
```

---

## Runbook Reference

### Immediate Mitigation

1. Edit ConfigMap to match environment variable values (temporary)
2. Rolling restart of affected deployments
3. Monitor connection success rate

### Proper Fix Required

The configuration loading order in `shared/config.py` needs to be corrected so that:
- Environment variables are read last, not first
- Or environment variables are merged after file loading

---

## Alert History

| Timestamp | Status | Notes |
|-----------|--------|-------|
| 03:17:42 | FIRING | Initial detection |
| 03:47:42 | FIRING | 30m check - still mismatched |
| 04:17:42 | FIRING | 1h - Paged on-call |
| 05:17:42 | FIRING | 2h - Escalated to P2 |
| 07:17:42 | FIRING | 4h - Auto-escalated to Critical |

---

## Notification Recipients

- **PagerDuty**: ionveil-platform-oncall
- **Slack**: #ionveil-alerts, #platform-incidents
- **Email**: platform-team@ionveil.io

---

## Related Alerts

- `database_connection_failures` - FIRING (correlated)
- `redis_cluster_unreachable` - FIRING (correlated)
- `request_latency_p99_high` - FIRING (symptom)
- `connection_pool_utilization` - CRITICAL (symptom)
