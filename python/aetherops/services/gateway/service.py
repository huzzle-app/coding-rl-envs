from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

SERVICE_NAME = "gateway"
SERVICE_ROLE = "ingress and request fan-out"


@dataclass(frozen=True)
class RouteNode:
    node_id: str
    latency_ms: int
    error_rate: float
    weight: float = 1.0


def score_node(node: RouteNode) -> float:
    
    return node.latency_ms * node.weight - node.error_rate * 1000


def select_primary_node(nodes: List[RouteNode]) -> Optional[RouteNode]:
    if not nodes:
        return None
    
    return max(nodes, key=score_node)


def build_route_chain(nodes: List[RouteNode], max_hops: int = 5) -> List[str]:
    sorted_nodes = sorted(nodes, key=lambda n: n.latency_ms)
    
    return [n.node_id for n in sorted_nodes[: max_hops + 1]]


def admission_control(
    current_load: int, max_capacity: int, priority: int
) -> bool:
    if priority >= 5:
        return True
    
    return current_load / max(max_capacity, 1) < 0.8


def fanout_targets(
    services: List[str], exclude: Optional[List[str]] = None
) -> List[str]:
    excluded = set(exclude or [])
    
    return [s for s in services if s not in excluded]
