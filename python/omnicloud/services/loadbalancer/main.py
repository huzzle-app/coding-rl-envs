"""
OmniCloud Load Balancer Service
Terminal Bench v2 - L4/L7 load balancer provisioning.

Contains bugs:
- D9: Load balancer health check flapping
- E6: Placement group capacity check (via compute scheduler)
"""
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException

logger = logging.getLogger(__name__)

app = FastAPI(title="OmniCloud LoadBalancer", version="1.0.0")


@dataclass
class HealthCheckState:
    """Tracks health check state for a target."""
    target_id: str = ""
    healthy: bool = True
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    last_check_time: float = 0.0
    
    healthy_threshold: int = 1  # Should be 3
    unhealthy_threshold: int = 1  # Should be 3

    def record_check(self, success: bool):
        """Record a health check result.

        BUG D9: With thresholds of 1, a single failed check marks target
        unhealthy, and a single success marks it healthy again, causing flapping.
        """
        self.last_check_time = time.time()
        if success:
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            if self.consecutive_successes >= self.healthy_threshold:
                self.healthy = True
        else:
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            if self.consecutive_failures >= self.unhealthy_threshold:
                self.healthy = False


@dataclass
class LoadBalancerConfig:
    """Load balancer configuration."""
    lb_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    lb_type: str = "application"  # "application" (L7) or "network" (L4)
    targets: List[Dict[str, Any]] = field(default_factory=list)
    health_checks: Dict[str, HealthCheckState] = field(default_factory=dict)
    algorithm: str = "round_robin"


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "loadbalancer"}


@app.post("/api/v1/loadbalancers")
async def create_lb(data: Dict[str, Any]):
    """Create a load balancer."""
    return {"lb_id": str(uuid.uuid4()), "status": "creating"}


@app.get("/api/v1/loadbalancers/{lb_id}")
async def get_lb(lb_id: str):
    """Get load balancer details."""
    return {"lb_id": lb_id, "status": "active"}


def distribute_traffic_weights(
    targets: List[Dict[str, Any]],
    total_weight: int = 100,
) -> List[Dict[str, Any]]:
    """Distribute traffic weights across targets to sum to total_weight.

    Each target gets a proportional share based on its capacity.
    Integer rounding remainders are distributed to the highest-capacity
    targets first.
    """
    if not targets:
        return []

    total_capacity = sum(t.get("capacity", 1) for t in targets)
    if total_capacity == 0:
        per_target = total_weight // len(targets)
        return [{**t, "weight": per_target} for t in targets]

    weighted = []
    for target in targets:
        capacity = target.get("capacity", 1)
        proportion = capacity / total_capacity
        weight = int(proportion * total_weight)
        weighted.append({**target, "weight": weight})

    return weighted


@dataclass
class WeightedRoundRobin:
    """Weighted round-robin load balancer."""
    targets: List[Dict[str, Any]] = field(default_factory=list)
    _current_index: int = 0
    _current_weight: int = 0

    def next_target(self) -> Optional[Dict[str, Any]]:
        """Get the next target based on weighted round-robin."""
        if not self.targets:
            return None

        max_weight = max(t.get("weight", 1) for t in self.targets)
        gcd_weight = self._gcd_weights()

        iterations = 0
        max_iterations = len(self.targets) * max_weight

        while iterations < max_iterations:
            self._current_index = (self._current_index + 1) % len(self.targets)
            if self._current_index == 0:
                self._current_weight -= gcd_weight
                if self._current_weight <= 0:
                    self._current_weight = max_weight

            target = self.targets[self._current_index]
            if target.get("weight", 1) >= self._current_weight:
                return target

            iterations += 1

        return self.targets[0]

    def _gcd_weights(self) -> int:
        """Compute GCD of all target weights."""
        from math import gcd
        weights = [t.get("weight", 1) for t in self.targets]
        result = weights[0]
        for w in weights[1:]:
            result = gcd(result, w)
        return result


def calculate_connection_drain_timeout(
    active_connections: int,
    avg_request_duration_ms: float,
    safety_factor: float = 2.0,
) -> float:
    """Calculate timeout for draining connections during target removal.

    Returns timeout in seconds.
    """
    if active_connections == 0:
        return 0.0
    # Estimate time for all in-flight requests to complete
    estimated_drain_ms = avg_request_duration_ms * safety_factor
    return estimated_drain_ms / 1000.0
