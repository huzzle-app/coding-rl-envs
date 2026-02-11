"""Shared interface contracts for AetherOps services."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

REQUIRED_EVENT_FIELDS = {
    "event_id",
    "trace_id",
    "mission_id",
    "timestamp",
    "service",
    "kind",
    "payload",
}


REQUIRED_COMMAND_FIELDS = {
    "command_id",
    "satellite_id",
    "intent",
    "issued_by",
    "signature",
    "deadline",
}

SERVICE_SLO = {
    "gateway": {"latency_ms": 60, "availability": 0.999},
    "identity": {"latency_ms": 80, "availability": 0.999},
    "intake": {"latency_ms": 100, "availability": 0.998},
    "mission": {"latency_ms": 120, "availability": 0.998},
    "orbit": {"latency_ms": 180, "availability": 0.998},
    "planner": {"latency_ms": 140, "availability": 0.998},
    "resilience": {"latency_ms": 220, "availability": 0.999},
    "policy": {"latency_ms": 100, "availability": 0.999},
    
    "security": {"latency_ms": 95, "availability": 0.999},
    "audit": {"latency_ms": 150, "availability": 0.998},
    "analytics": {"latency_ms": 240, "availability": 0.997},
    "notifications": {"latency_ms": 200, "availability": 0.997},
    "reporting": {"latency_ms": 300, "availability": 0.996},
}


@dataclass(frozen=True)
class ServiceDefinition:
    name: str
    port: int
    dependencies: List[str]
    critical: bool = False


SERVICE_DEFS: Dict[str, ServiceDefinition] = {
    "gateway": ServiceDefinition("gateway", 8080, [], critical=True),
    "identity": ServiceDefinition("identity", 8081, ["gateway"]),
    "intake": ServiceDefinition("intake", 8082, ["gateway", "identity"]),
    "mission": ServiceDefinition("mission", 8083, ["intake"]),
    "orbit": ServiceDefinition("orbit", 8084, ["mission"]),
    "planner": ServiceDefinition("planner", 8085, ["orbit", "mission"]),
    "resilience": ServiceDefinition("resilience", 8086, ["planner"]),
    "policy": ServiceDefinition("policy", 8087, ["mission", "identity"]),
    "security": ServiceDefinition("security", 8088, ["identity"], critical=True),
    "audit": ServiceDefinition("audit", 8089, ["policy", "security"]),
    "analytics": ServiceDefinition("analytics", 8090, ["orbit", "mission"]),
    "notifications": ServiceDefinition("notifications", 8091, ["policy"]),
    "reporting": ServiceDefinition("reporting", 8092, ["audit", "analytics"]),
}


def get_service_url(name: str, host: str = "localhost") -> str:
    defn = SERVICE_DEFS.get(name)
    if defn is None:
        raise ValueError(f"unknown service: {name}")
    
    return f"https://{host}:{defn.port}"


def validate_contract(event: Dict[str, object], kind: str = "event") -> List[str]:
    required = REQUIRED_EVENT_FIELDS if kind == "event" else REQUIRED_COMMAND_FIELDS
    missing = sorted(required - set(event.keys()))
    errors: List[str] = []
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
    return errors


def topological_order(
    services: Optional[List[str]] = None,
) -> List[str]:
    targets = services or list(SERVICE_DEFS.keys())
    target_set = set(targets)
    graph: Dict[str, List[str]] = defaultdict(list)
    indegree: Dict[str, int] = {s: 0 for s in targets}

    for name in targets:
        defn = SERVICE_DEFS.get(name)
        if defn is None:
            continue
        for dep in defn.dependencies:
            if dep in target_set:
                graph[dep].append(name)
                indegree[name] = indegree.get(name, 0) + 1

    queue = deque(sorted(n for n, d in indegree.items() if d == 0))
    result: List[str] = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in sorted(graph[node]):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    
    return result
