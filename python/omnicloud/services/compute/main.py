"""
OmniCloud Compute Service
Terminal Bench v2 - VM/container provisioning and scheduling.

Contains bugs:
- E1: Bin packing over-commit - float imprecision in capacity calculation
- E2: Affinity rule evaluation order wrong
- E3: Anti-affinity constraint race condition
- E4: Resource limit enforcement uses float comparison
- E5: Spot preemption notification dropped
- E6: Placement group capacity off-by-one
- E7: Node drain race - new workload scheduled during drain
- E8: Reservation expiry not cleaned up
"""
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException

logger = logging.getLogger(__name__)

app = FastAPI(title="OmniCloud Compute", version="1.0.0")


@dataclass
class ComputeNode:
    """A physical or virtual compute node."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    region: str = "us-east-1"
    
    total_cpu: float = 64.0
    total_memory_gb: float = 256.0
    used_cpu: float = 0.0
    used_memory_gb: float = 0.0
    is_draining: bool = False
    placement_groups: List[str] = field(default_factory=list)

    @property
    def available_cpu(self) -> float:
        """BUG E1: Float subtraction causes precision loss."""
        return self.total_cpu - self.used_cpu

    @property
    def available_memory_gb(self) -> float:
        return self.total_memory_gb - self.used_memory_gb


@dataclass
class PlacementGroup:
    """A placement group for co-located instances."""
    group_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    max_instances: int = 10
    current_instances: List[str] = field(default_factory=list)

    def has_capacity(self) -> bool:
        """Check if placement group has capacity.

        BUG E6: Off-by-one - allows max_instances + 1 instances.
        """
        
        return len(self.current_instances) <= self.max_instances


@dataclass
class Reservation:
    """A resource reservation with expiry."""
    reservation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    cpu: float = 0.0
    memory_gb: float = 0.0
    expires_at: float = 0.0
    node_id: str = ""

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


@dataclass
class Scheduler:
    """Resource scheduler with bin packing."""
    nodes: Dict[str, ComputeNode] = field(default_factory=dict)
    placement_groups: Dict[str, PlacementGroup] = field(default_factory=dict)
    reservations: Dict[str, Reservation] = field(default_factory=dict)
    affinity_rules: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    anti_affinity_rules: Dict[str, List[str]] = field(default_factory=dict)

    def schedule(
        self,
        tenant_id: str,
        cpu: float,
        memory_gb: float,
        affinity: Optional[Dict[str, Any]] = None,
        anti_affinity: Optional[List[str]] = None,
        placement_group_id: Optional[str] = None,
    ) -> Optional[str]:
        """Schedule a workload on a node.

        BUG E1: Float imprecision in capacity checks.
        BUG E2: Affinity rules evaluated in wrong order.
        BUG E3: No lock on anti-affinity check - race condition.
        BUG E7: Doesn't check is_draining flag properly.
        """
        candidates = []

        for node_id, node in self.nodes.items():
            
            if node.is_draining:
                continue

            
            if node.available_cpu >= cpu and node.available_memory_gb >= memory_gb:
                candidates.append(node_id)

        if not candidates:
            return None

        
        # but here anti-affinity is checked first
        if anti_affinity:
            
            candidates = [
                nid for nid in candidates
                if not any(
                    excluded in self.nodes[nid].placement_groups
                    for excluded in anti_affinity
                )
            ]

        if affinity:
            preferred_region = affinity.get("region")
            if preferred_region:
                regional = [
                    nid for nid in candidates
                    if self.nodes[nid].region == preferred_region
                ]
                if regional:
                    candidates = regional

        if not candidates:
            return None

        # Best-fit bin packing
        best_node = min(
            candidates,
            key=lambda nid: self.nodes[nid].available_cpu,
        )

        node = self.nodes[best_node]
        node.used_cpu += cpu
        node.used_memory_gb += memory_gb

        return best_node

    def cleanup_expired_reservations(self) -> int:
        """Clean up expired reservations.

        BUG E8: Expired reservations are removed from the dict but
        their resources are not released back to the node.
        """
        expired = [
            rid for rid, res in self.reservations.items()
            if res.is_expired()
        ]
        for rid in expired:
            
            # reservation = self.reservations[rid]
            # node = self.nodes.get(reservation.node_id)
            # if node:
            #     node.used_cpu -= reservation.cpu
            #     node.used_memory_gb -= reservation.memory_gb
            del self.reservations[rid]
        return len(expired)

    def check_resource_limit(self, requested: float, limit: float) -> bool:
        """Check if requested resources are within limit.

        BUG E4: Float comparison loses precision for resource limits.
        """
        
        return requested <= limit


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "compute"}


@app.post("/api/v1/instances")
async def create_instance(data: Dict[str, Any]):
    """Create a compute instance."""
    return {"instance_id": str(uuid.uuid4()), "status": "creating"}


@app.get("/api/v1/instances/{instance_id}")
async def get_instance(instance_id: str):
    """Get instance details."""
    return {"instance_id": instance_id, "status": "active"}


def rebalance_nodes(
    scheduler: Scheduler,
    source_node_id: str,
    target_node_id: str,
    cpu_to_move: float,
    memory_to_move: float,
) -> bool:
    """Move workload from source node to target node.

    Validates capacity on both sides, then adjusts resource tracking.
    """
    source = scheduler.nodes.get(source_node_id)
    target = scheduler.nodes.get(target_node_id)

    if not source or not target:
        return False

    if source.used_cpu < cpu_to_move or source.used_memory_gb < memory_to_move:
        return False

    if target.available_cpu < cpu_to_move or target.available_memory_gb < memory_to_move:
        return False

    target.used_cpu += cpu_to_move
    target.used_memory_gb += memory_to_move

    return True


def calculate_cluster_fragmentation(
    scheduler: Scheduler,
) -> float:
    """Calculate cluster resource fragmentation score.

    Fragmentation is 0.0 (perfectly consolidated) to 1.0 (fully fragmented).
    Measures how scattered free resources are across nodes relative to
    the cluster's capacity.
    """
    if not scheduler.nodes:
        return 0.0

    cluster_capacity = sum(n.total_cpu for n in scheduler.nodes.values())
    if cluster_capacity == 0:
        return 0.0

    free_per_node = [n.available_cpu for n in scheduler.nodes.values()]
    total_free = sum(free_per_node)
    if total_free == 0:
        return 0.0

    largest_free_block = max(free_per_node)
    return 1.0 - (largest_free_block / cluster_capacity)


def try_schedule_batch(
    scheduler: Scheduler,
    workloads: List[Dict[str, Any]],
) -> List[Optional[str]]:
    """Schedule multiple workloads, all-or-nothing.

    If any workload fails to schedule, all should be rolled back.
    """
    results = []
    allocations = []  # Track (node_id, cpu, memory) for rollback

    for workload in workloads:
        node_id = scheduler.schedule(
            workload.get("tenant_id", ""),
            workload.get("cpu", 0.0),
            workload.get("memory_gb", 0.0),
            workload.get("affinity"),
            workload.get("anti_affinity"),
        )
        results.append(node_id)
        if node_id:
            allocations.append((
                node_id,
                workload.get("cpu", 0.0),
                workload.get("memory_gb", 0.0),
            ))
        else:
            # Rollback previous allocations
            for alloc_node, alloc_cpu, alloc_mem in allocations:
                node = scheduler.nodes.get(alloc_node)
                if node:
                    node.used_cpu -= alloc_cpu
                    node.used_memory_gb -= alloc_mem
            return [None] * len(workloads)

    return results


def find_best_migration_target(
    scheduler: Scheduler,
    cpu_needed: float,
    memory_needed: float,
    exclude_nodes: Optional[List[str]] = None,
) -> Optional[str]:
    """Find the best node to migrate a workload to.

    Selects the node with the most available resources that
    isn't in the exclude list.
    """
    exclude = set(exclude_nodes or [])
    best_node = None
    best_available = -1.0

    for node_id, node in scheduler.nodes.items():
        if node_id in exclude or node.is_draining:
            continue
        if node.available_cpu >= cpu_needed and node.available_memory_gb >= memory_needed:
            available = node.available_cpu + node.available_memory_gb
            if available > best_available:
                best_available = available
                best_node = node_id

    return best_node
