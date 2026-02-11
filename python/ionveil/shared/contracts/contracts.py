"""IonVeil Service Contracts

Defines the canonical service names, ports, and health-check paths for all 10
microservices in the IonVeil planetary emergency command platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Service definitions
# ---------------------------------------------------------------------------

SERVICE_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "gateway": {
        "id": "gateway",
        "port": 8100,
        "health": "/health",
        "description": "API gateway and request router",
        "deps": [],
    },
    "identity": {
        "id": "identity",
        "port": 8101,
        "health": "/health",
        "description": "Authentication and authorisation service",
        "deps": ["gateway"],
    },
    "intake": {
        "id": "intake",
        "port": 8102,
        "health": "/health",
        "description": "Incident intake and triage",
        "deps": ["identity"],
    },
    "dispatch": {
        "id": "dispatch",
        "port": 8103,
        "health": "/health",
        "description": "Resource dispatch and assignment engine",
        "deps": ["identity", "intake"],
    },
    "routing": {
        "id": "routing",
        "port": 8104,
        "health": "/health",
        "description": "Geospatial routing and ETA calculation",
        "deps": ["dispatch"],
    },
    "policy": {
        "id": "policy",
        "port": 8105,
        "health": "/health",
        "description": "Escalation policy and SLA enforcement",
        "deps": ["identity"],
    },
    "notifications": {
        "id": "notifications",
        "port": 8106,
        "health": "/health",
        "description": "Multi-channel notification delivery",
        "deps": ["identity"],
    },
    "analytics": {
        "id": "analytics",
        "port": 8107,
        "health": "/health",
        "description": "Response-time analytics and reporting",
        "deps": ["dispatch", "routing"],
    },
    "audit": {
        "id": "audit",
        "port": 8108,
        "health": "/health",
        "description": "Compliance audit trail and event store",
        "deps": ["identity"],
    },
    "security": {
        "id": "security",
        "port": 8109,
        "health": "/health",
        "description": "Threat detection and access control",
        "deps": ["identity"],
    },
}

SERVICE_NAMES = list(SERVICE_CONTRACTS.keys())

SERVICE_PORTS: Dict[str, int] = {
    name: info["port"] for name, info in SERVICE_CONTRACTS.items()
}

# Backward-compatible alias used by tests and older integrations.
CONTRACTS = SERVICE_CONTRACTS


# ---------------------------------------------------------------------------
# Service registry helpers
# ---------------------------------------------------------------------------

@dataclass
class ServiceDefinition:
    name: str
    port: int
    health: str
    description: str
    deps: List[str] = field(default_factory=list)


SERVICE_DEFS: Dict[str, ServiceDefinition] = {
    name: ServiceDefinition(
        name=info["id"],
        port=info["port"],
        health=info["health"],
        description=info["description"],
        deps=info.get("deps", []),
    )
    for name, info in SERVICE_CONTRACTS.items()
}


def get_service_url(name: str, host: str = "localhost") -> str:
    svc = SERVICE_CONTRACTS.get(name)
    if svc is None:
        raise KeyError(f"unknown service: {name}")
    return f"http://{host}:{svc['port']}"


def validate_contract(name: str) -> List[str]:
    errors: List[str] = []
    svc = SERVICE_CONTRACTS.get(name)
    if svc is None:
        errors.append(f"service {name} not found")
        return errors
    if not svc.get("id"):
        errors.append("missing id")
    if not isinstance(svc.get("port"), int):
        errors.append("port must be int")
    if not svc.get("health"):
        errors.append("missing health endpoint")
    for dep in svc.get("deps", []):
        if dep not in SERVICE_CONTRACTS:
            errors.append(f"unknown dependency: {dep}")
    return errors


def topological_order() -> List[str]:
    in_degree: Dict[str, int] = {name: 0 for name in SERVICE_CONTRACTS}
    for name, info in SERVICE_CONTRACTS.items():
        for dep in info.get("deps", []):
            if dep in in_degree:
                in_degree[name] += 1
    queue = [n for n, d in in_degree.items() if d == 0]
    result: List[str] = []
    while queue:
        queue.sort()
        node = queue.pop(0)
        result.append(node)
        for name, info in SERVICE_CONTRACTS.items():
            if node in info.get("deps", []):
                in_degree[name] -= 1
                if in_degree[name] == 0:
                    queue.append(name)
    return result
