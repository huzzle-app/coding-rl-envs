"""
OmniCloud Infrastructure State Manager
Terminal Bench v2 - Manages desired vs actual state of cloud resources.

Contains bugs:
- A1: State machine transition race - concurrent transitions corrupt state
- A2: Eventual consistency violation - reads return stale during convergence
- A4: Desired vs actual state drift uses wrong comparison
- A5: Resource dependency graph cycle not detected
- A9: Concurrent modification lost update - no optimistic concurrency control
- A11: State snapshot corruption on concurrent writes
"""
import time
import uuid
import json
import copy
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ResourceState(Enum):
    PENDING = "pending"
    CREATING = "creating"
    ACTIVE = "active"
    UPDATING = "updating"
    DELETING = "deleting"
    DELETED = "deleted"
    FAILED = "failed"


VALID_TRANSITIONS = {
    ResourceState.PENDING: {ResourceState.CREATING, ResourceState.DELETED},
    ResourceState.CREATING: {ResourceState.ACTIVE, ResourceState.FAILED},
    ResourceState.ACTIVE: {ResourceState.UPDATING, ResourceState.DELETING},
    ResourceState.UPDATING: {ResourceState.ACTIVE, ResourceState.FAILED},
    ResourceState.DELETING: {ResourceState.DELETED, ResourceState.FAILED},
    ResourceState.DELETED: set(),
    ResourceState.FAILED: {ResourceState.PENDING, ResourceState.DELETING},
}


@dataclass
class Resource:
    """An infrastructure resource with state."""
    resource_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_type: str = ""
    name: str = ""
    tenant_id: str = ""
    state: ResourceState = ResourceState.PENDING
    desired_config: Dict[str, Any] = field(default_factory=dict)
    actual_config: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    version: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class StateManager:
    """Manages the infrastructure state for all resources."""
    resources: Dict[str, Resource] = field(default_factory=dict)
    _snapshots: Dict[str, bytes] = field(default_factory=dict)
    
    _state_version: int = 0

    def transition_state(self, resource_id: str, new_state: ResourceState) -> bool:
        """Transition a resource to a new state.

        BUG A1: No locking on state transitions. Concurrent transitions can
        corrupt the state machine (e.g., two threads both see ACTIVE and
        transition to UPDATING and DELETING simultaneously).
        """
        resource = self.resources.get(resource_id)
        if not resource:
            return False

        
        if new_state not in VALID_TRANSITIONS.get(resource.state, set()):
            logger.warning(
                f"Invalid transition {resource.state} -> {new_state} "
                f"for resource {resource_id}"
            )
            return False

        resource.state = new_state
        resource.version += 1
        resource.updated_at = time.time()
        return True

    def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get a resource by ID.

        BUG A2: Returns resource directly without checking if state is
        converged. During eventual consistency windows, this can return
        a resource whose actual_config doesn't match desired_config
        without any staleness indicator.
        """
        
        return self.resources.get(resource_id)

    def detect_drift(self, resource_id: str) -> bool:
        """Detect if resource has drifted from desired state.

        BUG A4: Uses equality comparison on dicts which doesn't handle
        floating-point values, ordering of lists, or None vs missing keys.
        """
        resource = self.resources.get(resource_id)
        if not resource:
            return False

        
        return resource.desired_config != resource.actual_config

    def update_resource(
        self,
        resource_id: str,
        config: Dict[str, Any],
        expected_version: Optional[int] = None,
    ) -> bool:
        """Update a resource's desired configuration.

        BUG A9: The expected_version parameter is accepted but ignored.
        No optimistic concurrency control - concurrent updates result in
        lost updates (last writer wins).
        """
        resource = self.resources.get(resource_id)
        if not resource:
            return False

        
        resource.desired_config = config
        resource.version += 1
        resource.updated_at = time.time()
        return True

    def build_dependency_graph(self) -> Dict[str, Set[str]]:
        """Build the dependency graph of all resources.

        BUG A5: Does not detect cycles in the dependency graph.
        This can cause infinite loops during planning/provisioning.
        """
        graph: Dict[str, Set[str]] = {}
        for rid, resource in self.resources.items():
            graph[rid] = set(resource.dependencies)

        
        return graph

    def take_snapshot(self, snapshot_id: str) -> bytes:
        """Take a snapshot of the current state.

        BUG A11: No locking during snapshot creation. Concurrent writes during
        snapshot can corrupt the snapshot (partial state captured).
        """
        
        state_data = {}
        for rid, resource in self.resources.items():
            state_data[rid] = {
                "resource_type": resource.resource_type,
                "name": resource.name,
                "tenant_id": resource.tenant_id,
                "state": resource.state.value,
                "desired_config": resource.desired_config,
                "actual_config": resource.actual_config,
                "dependencies": resource.dependencies,
                "version": resource.version,
            }
        snapshot = json.dumps(state_data).encode("utf-8")
        self._snapshots[snapshot_id] = snapshot
        return snapshot

    def restore_snapshot(self, snapshot_id: str) -> bool:
        """Restore state from a snapshot."""
        snapshot_data = self._snapshots.get(snapshot_id)
        if not snapshot_data:
            return False

        state_data = json.loads(snapshot_data.decode("utf-8"))
        self.resources.clear()
        for rid, data in state_data.items():
            self.resources[rid] = Resource(
                resource_id=rid,
                resource_type=data["resource_type"],
                name=data["name"],
                tenant_id=data["tenant_id"],
                state=ResourceState(data["state"]),
                desired_config=data["desired_config"],
                actual_config=data["actual_config"],
                dependencies=data["dependencies"],
                version=data["version"],
            )
        return True

    def add_resource(self, resource: Resource) -> str:
        """Add a new resource to the state."""
        self.resources[resource.resource_id] = resource
        self._state_version += 1
        return resource.resource_id

    def remove_resource(self, resource_id: str) -> bool:
        """Remove a resource from the state."""
        if resource_id in self.resources:
            del self.resources[resource_id]
            self._state_version += 1
            return True
        return False

    def batch_transition(
        self,
        transitions: List[Tuple[str, ResourceState]],
    ) -> Dict[str, bool]:
        """Transition multiple resources atomically.

        All transitions should succeed or all should be rolled back.
        """
        results = {}
        completed = []
        original_states = {}

        for resource_id, new_state in transitions:
            resource = self.resources.get(resource_id)
            if resource:
                original_states[resource_id] = resource.state

            success = self.transition_state(resource_id, new_state)
            results[resource_id] = success

            if success:
                completed.append(resource_id)
            else:
                # Roll back completed transitions on failure
                for rid in completed:
                    r = self.resources.get(rid)
                    if r and rid in original_states:
                        r.state = original_states[rid]
                break

        return results

    def merge_states(self, other: 'StateManager') -> int:
        """Merge another state manager's resources into this one.

        Resources from ``other`` take precedence when they have a higher
        version number. Returns the count of resources merged.
        """
        merged_count = 0
        for rid, incoming in other.resources.items():
            current = self.resources.get(rid)
            if current is None or incoming.version > current.version:
                self.resources[rid] = incoming
                merged_count += 1
        return merged_count

    def get_resources_by_state(
        self,
        state: ResourceState,
        tenant_id: Optional[str] = None,
    ) -> List[Resource]:
        """Get all resources in a given state, optionally filtered by tenant."""
        results = []
        for resource in self.resources.values():
            if resource.state == state:
                if tenant_id is None or resource.tenant_id is not None:
                    results.append(resource)
        return results

    def transition_with_precondition(
        self,
        resource_id: str,
        new_state: ResourceState,
        precondition: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Transition with a precondition check on resource config.

        The precondition dict specifies required config values that must
        match the resource's desired_config for the transition to proceed.
        """
        resource = self.resources.get(resource_id)
        if not resource:
            return False

        success = self.transition_state(resource_id, new_state)

        if precondition and success:
            for key, expected in precondition.items():
                if resource.desired_config.get(key) != expected:
                    return False

        return success

    def clone_resource(self, resource_id: str, new_id: Optional[str] = None) -> Optional[str]:
        """Create a clone of an existing resource with a fresh state."""
        source = self.resources.get(resource_id)
        if not source:
            return None

        clone_id = new_id or str(uuid.uuid4())
        cloned = Resource(
            resource_id=clone_id,
            resource_type=source.resource_type,
            name=f"{source.name}-clone",
            tenant_id=source.tenant_id,
            state=ResourceState.PENDING,
            desired_config=dict(source.desired_config),
            actual_config=dict(source.actual_config),
            dependencies=source.dependencies,
            version=0,
        )
        self.resources[clone_id] = cloned
        self._state_version += 1
        return clone_id
