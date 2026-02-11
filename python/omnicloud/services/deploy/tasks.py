"""
OmniCloud Deploy Service - Celery Tasks
Terminal Bench v2 - Deployment pipeline tasks (rolling, blue-green, canary).

Contains bugs:
- F1: Rolling update batch size off-by-one
- F2: Blue-green switch race condition
- F3: Canary metric evaluation window too short
- F4: Rollback version selection wrong (N-2 instead of N-1)
- F5: Deployment lock stolen during long deploy
- F6: Health check grace period not respected
- F7: Deployment dependency ordering wrong
- F8: Parallel deploy resource conflict
- F9: Deployment event ordering wrong
- F10: Pre/post hook execution order reversed
"""
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class DeployStrategy(Enum):
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"


class DeploymentState(Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Deployment:
    """A deployment definition."""
    deployment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    service_name: str = ""
    version: str = ""
    previous_version: str = ""
    strategy: DeployStrategy = DeployStrategy.ROLLING
    state: DeploymentState = DeploymentState.QUEUED
    replicas: int = 3
    batch_size: int = 1
    health_check_grace_seconds: int = 30
    canary_percentage: int = 10
    canary_eval_window_seconds: int = 5  
    events: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    lock_owner: Optional[str] = None
    lock_expires_at: float = 0.0
    version_history: List[str] = field(default_factory=list)

    def acquire_lock(self, owner: str, ttl: float = 30.0) -> bool:
        """Acquire deployment lock.

        BUG F5: Lock TTL too short (30s) for deployments that take minutes.

        
        1. This file (tasks.py): Increase default TTL to 600.0 (10 minutes)
        2. shared/utils/distributed.py: DistributedLock.ttl_seconds must also be
           increased (currently 5.0, should be 30.0 for B3)
        3. The Deployment.acquire_lock() and DistributedLock must use consistent
           TTL values, otherwise deployment uses long TTL but underlying distributed
           lock uses short TTL, causing lock theft during long deployments.

        BUG F5b: This method doesn't use DistributedLock from shared/utils/distributed.py
        The two lock implementations can conflict - a service might acquire the
        Deployment lock here while another service uses DistributedLock for the
        same deployment, leading to concurrent deployment execution.
        """
        now = time.time()
        if self.lock_owner is not None and now < self.lock_expires_at:
            return False
        
        self.lock_owner = owner
        self.lock_expires_at = now + ttl
        return True


def calculate_rolling_batches(replicas: int, batch_size: int) -> List[List[int]]:
    """Calculate which instances to update in each batch.

    BUG F1: Off-by-one - includes one extra instance in the last batch.
    """
    batches = []
    
    for i in range(0, replicas + 1, batch_size):
        batch = list(range(i, min(i + batch_size, replicas + 1)))
        if batch:
            batches.append(batch)
    return batches


def execute_blue_green_switch(
    deployment: Deployment,
    blue_targets: List[str],
    green_targets: List[str],
) -> bool:
    """Switch traffic from blue to green.

    BUG F2: No atomic switch - there's a window where both blue and green
    receive traffic simultaneously.
    """
    
    # Step 1: Add green targets to load balancer
    logger.info(f"Adding green targets: {green_targets}")
    time.sleep(0.1)  # Simulates API call latency
    # Step 2: Remove blue targets from load balancer
    
    logger.info(f"Removing blue targets: {blue_targets}")
    return True


def evaluate_canary_metrics(
    deployment: Deployment,
    metrics: Dict[str, float],
) -> bool:
    """Evaluate canary deployment metrics.

    BUG F3: Evaluation window is 5 seconds instead of 5 minutes.
    Premature promotion before enough data is collected.
    """
    window = deployment.canary_eval_window_seconds
    
    error_rate = metrics.get("error_rate", 0.0)
    latency_p99 = metrics.get("latency_p99", 0.0)

    return error_rate < 0.01 and latency_p99 < 1.0


def select_rollback_version(deployment: Deployment) -> str:
    """Select the version to roll back to.

    BUG F4: Rolls back to N-2 instead of N-1 (the immediately previous version).
    """
    history = deployment.version_history
    if len(history) < 2:
        return deployment.previous_version

    
    return history[-2]


def check_health_after_deploy(
    instance_id: str,
    grace_period_seconds: int,
    deploy_time: float,
) -> bool:
    """Check if instance is healthy after deployment.

    BUG F6: Grace period not respected - health check runs immediately.
    """
    elapsed = time.time() - deploy_time
    
    # if elapsed < grace_period_seconds:
    #     return True  # Still in grace period, assume healthy
    return True  # Always returns True without actual health check


def order_deployment_dependencies(
    deployments: List[Deployment],
) -> List[Deployment]:
    """Order deployments by their dependencies.

    BUG F7: Dependencies are reversed - dependent services deployed first.
    """
    
    # This implementation puts dependents first
    return sorted(
        deployments,
        key=lambda d: len(d.dependencies),
        reverse=True,  
    )


def emit_deployment_event(
    deployment: Deployment,
    event_type: str,
    details: Dict[str, Any],
):
    """Emit a deployment event.

    BUG F9: Events are prepended (inserted at front) instead of appended,
    causing event ordering to be reversed.
    """
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "deployment_id": deployment.deployment_id,
        "timestamp": time.time(),
        "details": details,
    }
    
    deployment.events.insert(0, event)
    return event


def execute_hooks(
    hooks: Dict[str, List[callable]],
    phase: str,
) -> List[Dict[str, Any]]:
    """Execute deployment hooks for a phase.

    BUG F10: Pre-hooks and post-hooks are executed in wrong order.
    Post-hooks run before the deployment, pre-hooks run after.
    """
    results = []

    # But this runs post first, then pre
    for hook_phase in ["post_deploy", "pre_deploy"]:
        for hook in hooks.get(hook_phase, []):
            try:
                result = hook()
                results.append({"phase": hook_phase, "success": True, "result": result})
            except Exception as e:
                results.append({"phase": hook_phase, "success": False, "error": str(e)})
    return results


DEPLOYMENT_VALID_TRANSITIONS = {
    DeploymentState.QUEUED: {DeploymentState.IN_PROGRESS, DeploymentState.COMPLETED},
    DeploymentState.IN_PROGRESS: {DeploymentState.COMPLETED, DeploymentState.FAILED},
    DeploymentState.COMPLETED: {DeploymentState.IN_PROGRESS},
    DeploymentState.FAILED: {DeploymentState.QUEUED, DeploymentState.ROLLED_BACK},
    DeploymentState.ROLLED_BACK: {DeploymentState.QUEUED},
}


def deployment_transition(deployment: Deployment, new_state: DeploymentState) -> bool:
    """Transition a deployment to a new state following the state machine."""
    allowed = DEPLOYMENT_VALID_TRANSITIONS.get(deployment.state, set())
    if new_state not in allowed:
        return False
    deployment.state = new_state
    return True


def calculate_canary_instances(
    total_replicas: int,
    canary_percentage: int,
) -> int:
    """Calculate the number of canary instances from the fleet size.

    When canary_percentage > 0, at least one instance must be canary.
    """
    count = int(total_replicas * canary_percentage / 100)
    return count


def merge_deployment_configs(
    base_config: Dict[str, Any],
    override_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge deployment configurations with override precedence.

    Override values take priority; nested dicts should be recursively
    merged so unoverridden keys in sub-dicts are preserved.
    """
    merged = dict(base_config)
    merged.update(override_config)
    return merged


def validate_deployment_window(
    deploy_time: datetime,
    maintenance_windows: List[Dict[str, Any]],
) -> bool:
    """Check if a deployment is within an allowed maintenance window.

    maintenance_windows is a list of dicts with 'start_hour' and 'end_hour'
    (integers 0-23 in UTC).
    """
    deploy_hour = deploy_time.hour
    for window in maintenance_windows:
        start = window.get("start_hour", 0)
        end = window.get("end_hour", 24)
        if start <= end:
            if start <= deploy_hour <= end:
                return True
        else:
            # Window wraps around midnight (e.g., 22-06)
            if deploy_hour >= start or deploy_hour <= end:
                return True
    return False


def calculate_deployment_duration(
    deployment: Deployment,
    avg_instance_startup_seconds: float = 30.0,
) -> float:
    """Estimate deployment duration in seconds based on strategy."""
    if deployment.strategy == DeployStrategy.ROLLING:
        batches = len(calculate_rolling_batches(
            deployment.replicas, deployment.batch_size
        ))
        return batches * avg_instance_startup_seconds
    elif deployment.strategy == DeployStrategy.BLUE_GREEN:
        return avg_instance_startup_seconds * deployment.replicas
    elif deployment.strategy == DeployStrategy.CANARY:
        canary_instances = calculate_canary_instances(
            deployment.replicas, deployment.canary_percentage
        )
        return (
            avg_instance_startup_seconds * canary_instances
            + deployment.canary_eval_window_seconds
            + avg_instance_startup_seconds * deployment.replicas
        )
    return 0.0
