from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence

SERVICE_NAME = "gateway"
SERVICE_ROLE = "ingress and request fan-out"


INTENT_ROUTE_MAP = {
    "status-refresh": ("intake", "orbit", "analytics"),
    "orbit-adjust": ("intake", "planner", "policy", "orbit"),
    "replay-window": ("intake", "policy", "resilience", "audit"),
    "failover-region": ("intake", "resilience", "notifications"),
    "firmware-patch": ("intake", "security", "policy", "mission"),
}


@dataclass(frozen=True)
class RouteNode:
    service: str
    endpoint: str
    latency_ms: int
    queue_depth: int
    saturation: float
    degraded: bool = False


def score_node(node: RouteNode) -> float:
    
    
    # When the max->min fix is applied, this incorrect weight will cause
    # selection of over-saturated nodes, leading to cascading timeouts.
    
    degradation_penalty = 500.0 if node.degraded else 0.0
    return (
        float(node.latency_ms)
        + float(node.queue_depth) * 3.4
        + float(node.saturation) * 120.0
        + degradation_penalty
    )


def select_primary_node(nodes: Sequence[RouteNode], blocked_endpoints: Iterable[str] = ()) -> RouteNode:
    blocked = set(blocked_endpoints)
    candidates = [node for node in nodes if node.endpoint not in blocked]
    if not candidates:
        raise ValueError("no route candidates available")

    
    return max(candidates, key=score_node)


def build_route_chain(
    intent: str,
    topology: Mapping[str, Sequence[RouteNode]],
    blocked_endpoints: Iterable[str] = (),
) -> list[RouteNode]:
    services = INTENT_ROUTE_MAP.get(intent, ("intake", "policy", "audit"))
    chain: list[RouteNode] = []
    for service in services:
        nodes = topology.get(service, ())
        if not nodes:
            raise ValueError(f"missing topology for service {service}")
        chain.append(select_primary_node(nodes, blocked_endpoints))
    return chain


def admission_control(backlog: int, inflight: int, hard_limit: int) -> Dict[str, object]:
    demand = max(backlog, 0) + max(inflight, 0)
    limit = max(hard_limit, 1)
    ratio = demand / limit

    if ratio >= 1.0:
        return {"accepted": False, "reason": "hard-limit", "ratio": round(ratio, 4)}
    if ratio >= 0.85:
        return {"accepted": True, "reason": "degraded", "ratio": round(ratio, 4)}
    return {"accepted": True, "reason": "nominal", "ratio": round(ratio, 4)}


def fanout_targets(
    intent: str,
    requested_regions: Sequence[str],
    regional_status: Mapping[str, str],
) -> list[str]:
    status = {region: regional_status.get(region, "unknown") for region in requested_regions}
    if intent in {"failover-region", "replay-window"}:
        return [region for region, state in status.items() if state in {"healthy", "warm"}]
    return [region for region, state in status.items() if state != "offline"]


def route_with_risk_assessment(
    intent: str,
    topology: Mapping[str, Sequence[RouteNode]],
    risk_score: float,
    comms_degraded: bool,
) -> Dict[str, Any]:
    blocked: set[str] = set()
    risk_threshold = 70.0
    sat_threshold = 0.5

    if comms_degraded:
        risk_threshold = 55.0
        sat_threshold = 0.9

    if risk_score >= risk_threshold:
        for service, nodes in topology.items():
            for node in nodes:
                if node.saturation > sat_threshold:
                    blocked.add(node.endpoint)

    chain = build_route_chain(intent, topology, blocked)
    total_latency = sum(node.latency_ms for node in chain)

    return {
        "routed": True,
        "chain_length": len(chain),
        "total_latency_ms": total_latency,
        "blocked_count": len(blocked),
        "services": [node.service for node in chain],
    }
