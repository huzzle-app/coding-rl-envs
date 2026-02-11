"""Shared interface contracts for LatticeForge services."""

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
    "orbit": {"latency_ms": 180, "availability": 0.998},
    "planner": {"latency_ms": 140, "availability": 0.998},
    "resilience": {"latency_ms": 220, "availability": 0.999},
    "security": {"latency_ms": 95, "availability": 0.9995},
    "analytics": {"latency_ms": 240, "availability": 0.997},
}
