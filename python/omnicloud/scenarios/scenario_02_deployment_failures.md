# Scenario 2: Production Deployment Failures

## Slack Thread - #incidents Channel

---

**@sarah-chen (SRE Lead)** - 10:47 AM
:rotating_light: We're seeing widespread deployment failures across multiple services. Canary deployments are promoting way too fast, rolling updates are hitting more instances than expected, and I just saw two deployments running simultaneously on the same service.

**@mike-torres (Platform Engineer)** - 10:49 AM
I'm looking at the deploy logs now. The canary for `payment-gateway` was promoted after only 5 seconds of metrics collection. We normally wait 5 minutes to gather enough error rate data.

**@sarah-chen (SRE Lead)** - 10:51 AM
That explains why we pushed a buggy release to 100% traffic. We didn't have enough time to detect the elevated error rates.

**@jennifer-wu (DevOps)** - 10:53 AM
I tried to rollback `payment-gateway` but it went to v2.1.0 instead of v2.2.0. We deployed v2.3.0 which was bad, so rollback should have gone to v2.2.0, not skipped back two versions.

**@mike-torres (Platform Engineer)** - 10:55 AM
Wait, I also noticed the rolling update for `inventory-service` touched 4 instances when we have 3 replicas and batch_size=1. The deployment config shows:
```
replicas: 3
batch_size: 1
batches: [[0], [1], [2], [3]]  # Should be [[0], [1], [2]]
```

**@david-kim (Backend Lead)** - 10:58 AM
Blue-green switch for `order-processor` is causing 500 errors. During the switch, both old and new versions were receiving traffic simultaneously for about 100ms. Our service can't handle that - it caused data inconsistency.

**@sarah-chen (SRE Lead)** - 11:02 AM
@david-kim That's supposed to be an atomic switch. Traffic should go to blue OR green, never both.

**@jennifer-wu (DevOps)** - 11:05 AM
I found another issue. The `notification-service` deployment locked itself out. The deployment took 60 seconds but the lock TTL was only 30 seconds. Another deployment stole the lock mid-deploy.

**@alex-rivera (Junior SRE)** - 11:08 AM
Heads up - `analytics-pipeline` is timing health checks on newly deployed instances. The instance needs 45 seconds to warm up but health checks are failing immediately after deploy. Shouldn't there be a grace period?

**@sarah-chen (SRE Lead)** - 11:11 AM
We're also seeing dependency ordering issues. The `api-gateway` was deployed BEFORE `auth-service` even though api-gateway depends on auth-service. This caused a 2-minute outage during the deploy window.

**@mike-torres (Platform Engineer)** - 11:14 AM
Looking at deployment events, they're in reverse chronological order. The "deployment_completed" event appears BEFORE "deployment_started" in the event stream. This is breaking our alerting dashboards.

**@jennifer-wu (DevOps)** - 11:17 AM
One more thing - deployment hooks are running out of order. Post-deploy hooks are executing BEFORE pre-deploy hooks. The database migration (pre-deploy) ran AFTER the new code was deployed (post-deploy hook should run after).

---

## Grafana Alert Notifications

```
[FIRING] CanaryPromotedTooFast
  Service: payment-gateway
  Canary evaluation window: 5 seconds (expected: 300 seconds)
  Time since canary start: 7 seconds

[FIRING] DeploymentLockStolen
  Service: notification-service
  Original lock holder: deploy-worker-03
  Lock stolen by: deploy-worker-07
  Lock age when stolen: 32 seconds

[FIRING] RollbackVersionMismatch
  Service: payment-gateway
  Current version: v2.3.0
  Expected rollback: v2.2.0
  Actual rollback: v2.1.0
```

---

## Affected Components

- `services/deploy/tasks.py` - Rolling update, blue-green, canary logic
- `services/deploy/main.py` - Deployment orchestration
- `services/gateway/main.py` - Health check configuration

---

## Test Failures Related

```
FAILED tests/integration/test_deployment_pipeline.py::TestDeploymentPipeline::test_rolling_update_batch_count
FAILED tests/integration/test_deployment_pipeline.py::TestDeploymentPipeline::test_blue_green_atomic_switch
FAILED tests/integration/test_deployment_pipeline.py::TestDeploymentPipeline::test_canary_evaluation_window
FAILED tests/integration/test_deployment_pipeline.py::TestDeploymentPipeline::test_rollback_to_previous_version
FAILED tests/integration/test_deployment_pipeline.py::TestDeploymentPipeline::test_deployment_lock_duration
FAILED tests/integration/test_deployment_pipeline.py::TestDeploymentPipeline::test_health_check_grace_period
FAILED tests/integration/test_deployment_pipeline.py::TestDeploymentPipeline::test_deployment_dependency_order
FAILED tests/integration/test_deployment_pipeline.py::TestDeploymentPipeline::test_deployment_event_ordering
FAILED tests/integration/test_deployment_pipeline.py::TestDeploymentPipeline::test_hook_execution_order
```

---

## Impact

- **Availability**: 12-minute partial outage for payment-gateway
- **Data Integrity**: 47 orders processed with inconsistent state during blue-green overlap
- **Deployment Velocity**: Team is afraid to deploy; manual rollbacks required

---

## Relevant Metrics

| Metric | Expected | Actual |
|--------|----------|--------|
| Canary eval window | 300s | 5s |
| Rolling update batches (3 replicas) | 3 | 4 |
| Deployment lock TTL | 300s | 30s |
| Health check grace period | 60s | 0s |
