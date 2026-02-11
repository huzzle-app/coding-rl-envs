"""
HeliosOps — Emergency Dispatch Operations Platform
====================================================

Core domain library for real-time emergency dispatch, incident management,
routing, and response coordination.
"""

__version__ = "1.4.0"

from .dispatch import plan_dispatch, plan_dispatch_async, dispatch_batch
from .routing import choose_route, calculate_distance, optimize_multi_stop
from .policy import next_policy, check_sla_compliance, evaluate_escalation
from .security import verify_signature, validate_jwt, check_authorization
from .resilience import replay_events, CircuitBreaker, deduplicate
from .queue import should_shed, PriorityQueue, RateLimiter
from .statistics import percentile, track_response_time, generate_heatmap
from .workflow import can_transition, execute_transition, classify_incident
from .scheduler import schedule_task, check_sla_deadlines, recurring_task
from .geo import haversine, point_in_polygon, nearest_units
from .models import (
    DispatchOrder,
    Incident,
    Unit,
    Location,
    Assignment,
    Route,
    create_incident,
    create_unit,
)

__all__ = [
    # dispatch
    "plan_dispatch",
    "plan_dispatch_async",
    "dispatch_batch",
    # routing
    "choose_route",
    "calculate_distance",
    "optimize_multi_stop",
    # policy
    "next_policy",
    "check_sla_compliance",
    "evaluate_escalation",
    # security
    "verify_signature",
    "validate_jwt",
    "check_authorization",
    # resilience
    "replay_events",
    "CircuitBreaker",
    "deduplicate",
    # queue
    "should_shed",
    "PriorityQueue",
    "RateLimiter",
    # statistics
    "percentile",
    "track_response_time",
    "generate_heatmap",
    # workflow
    "can_transition",
    "execute_transition",
    "classify_incident",
    # scheduler
    "schedule_task",
    "check_sla_deadlines",
    "recurring_task",
    # geo
    "haversine",
    "point_in_polygon",
    "nearest_units",
    # models
    "DispatchOrder",
    "Incident",
    "Unit",
    "Location",
    "Assignment",
    "Route",
    "create_incident",
    "create_unit",
]

