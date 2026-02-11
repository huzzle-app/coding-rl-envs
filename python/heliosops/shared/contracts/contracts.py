"""
HeliosOps Service Contracts

Defines the canonical service names, ports, and health-check paths for all 10
microservices in the HeliosOps emergency dispatch platform.  Used by service
discovery, inter-service HTTP clients, and integration tests.
"""

from typing import Any, Dict

SERVICE_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "gateway": {
        "id": "gateway",
        "port": 8100,
        "health": "/health",
        "description": "API gateway and request router",
    },
    "identity": {
        "id": "identity",
        "port": 8101,
        "health": "/health",
        "description": "Authentication and authorisation service",
    },
    "intake": {
        "id": "intake",
        "port": 8102,
        "health": "/health",
        "description": "Incident intake and triage",
    },
    "dispatch": {
        "id": "dispatch",
        "port": 8103,
        "health": "/health",
        "description": "Resource dispatch and assignment engine",
    },
    "routing": {
        "id": "routing",
        "port": 8104,
        "health": "/health",
        "description": "Geospatial routing and ETA calculation",
    },
    "policy": {
        "id": "policy",
        "port": 8105,
        "health": "/health",
        "description": "Escalation policy and SLA enforcement",
    },
    "notifications": {
        "id": "notifications",
        "port": 8106,
        "health": "/health",
        "description": "Multi-channel notification delivery",
    },
    "analytics": {
        "id": "analytics",
        "port": 8107,
        "health": "/health",
        "description": "Response-time analytics and reporting",
    },
    "audit": {
        "id": "audit",
        "port": 8108,
        "health": "/health",
        "description": "Compliance audit trail and event store",
    },
    "security": {
        "id": "security",
        "port": 8109,
        "health": "/health",
        "description": "Threat detection and access control",
    },
}

# Convenience list of all service names
SERVICE_NAMES = list(SERVICE_CONTRACTS.keys())

# Quick lookup: service name -> port
SERVICE_PORTS: Dict[str, int] = {
    name: info["port"] for name, info in SERVICE_CONTRACTS.items()
}

