"""
OmniCloud Infrastructure Reconciler
Terminal Bench v2 - Reconciles desired vs actual state of resources.

Contains bugs:
- A3: Reconciliation loop runs infinitely - no max iteration bound
- A7: Partial apply rollback incomplete - orphaned partial resources
- A10: Orphaned resource cleanup misses resources with dangling references
- A12: Cross-region state sync lag unbounded
"""
import time
import logging
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field

from shared.infra.state import StateManager, Resource, ResourceState

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationResult:
    """Result of a reconciliation pass."""
    reconciled: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class Reconciler:
    """Reconciles infrastructure state."""
    state_manager: StateManager = field(default_factory=StateManager)
    
    max_iterations: int = 0  # 0 means unlimited - BUG: should be a reasonable limit like 100

    def reconcile(self) -> ReconciliationResult:
        """Run the reconciliation loop.

        BUG A3: When max_iterations is 0 (default), the loop has no bound.
        If a resource keeps flipping between states, this runs forever.
        """
        result = ReconciliationResult()
        iteration = 0

        while True:
            
            if self.max_iterations > 0 and iteration >= self.max_iterations:
                break

            changes_made = False
            for rid, resource in list(self.state_manager.resources.items()):
                if resource.state == ResourceState.ACTIVE:
                    if self.state_manager.detect_drift(rid):
                        self._reconcile_resource(rid, resource, result)
                        changes_made = True

            if not changes_made:
                break
            iteration += 1

        return result

    def _reconcile_resource(
        self,
        resource_id: str,
        resource: Resource,
        result: ReconciliationResult,
    ):
        """Reconcile a single resource."""
        try:
            self.state_manager.transition_state(resource_id, ResourceState.UPDATING)
            # Simulate applying desired config
            resource.actual_config = dict(resource.desired_config)
            self.state_manager.transition_state(resource_id, ResourceState.ACTIVE)
            result.reconciled += 1
        except Exception as e:
            result.failed += 1
            result.errors.append(f"Failed to reconcile {resource_id}: {e}")

    def apply_changes(
        self,
        resource_ids: List[str],
        configs: Dict[str, Dict[str, Any]],
    ) -> ReconciliationResult:
        """Apply configuration changes to multiple resources.

        BUG A7: On partial failure, already-applied changes are not rolled back.
        Resources that were successfully updated remain changed while later
        resources fail, leaving the system in an inconsistent state.
        """
        result = ReconciliationResult()
        applied: List[str] = []

        for rid in resource_ids:
            try:
                config = configs.get(rid, {})
                self.state_manager.update_resource(rid, config)
                applied.append(rid)
                result.reconciled += 1
            except Exception as e:
                result.failed += 1
                result.errors.append(f"Failed to apply {rid}: {e}")
                
                # for applied_rid in reversed(applied):
                #     self.state_manager.rollback_resource(applied_rid)
                break

        return result

    def cleanup_orphans(self) -> int:
        """Clean up orphaned resources.

        BUG A10: Only checks direct references, not transitive ones.
        Resources that are referenced by orphaned resources are not cleaned up.
        """
        orphaned_count = 0
        all_ids = set(self.state_manager.resources.keys())
        referenced_ids: Set[str] = set()

        for resource in self.state_manager.resources.values():
            referenced_ids.update(resource.dependencies)

        
        # If resource A -> B -> C, and A is deleted, B becomes orphan,
        # but C (which depends on B) is not detected as orphan
        for rid in list(all_ids):
            resource = self.state_manager.resources[rid]
            if resource.state == ResourceState.DELETED:
                continue
            # Check if any of this resource's dependencies are missing
            for dep_id in resource.dependencies:
                if dep_id not in all_ids:
                    logger.warning(f"Orphaned reference: {rid} -> {dep_id}")

        return orphaned_count

    def sync_regions(
        self,
        source_region: str,
        target_region: str,
        state: Dict[str, Any],
        max_lag_ms: int = 0,  
    ) -> bool:
        """Sync state across regions.

        BUG A12: No bounded convergence time. The sync operation has no
        deadline or maximum lag tracking, so stale reads can persist
        indefinitely.

        
        1. This file (reconciler.py): Add max_lag_ms parameter with default 5000
        2. shared/infra/state.py: StateManager must track last_sync_timestamp
           per region and expose get_sync_lag(region) method
        3. Both files must agree on lag calculation - reconciler checks lag,
           state.py provides the timestamp. Mismatched implementations cause:
           - Reconciler thinks sync is fresh, but StateManager has stale data
           - Or StateManager rejects valid syncs due to clock skew

        BUG A12b: Region sync uses eventual consistency without conflict resolution
        
        are silently overwritten by the last write. Fixing A12 (adding lag bounds)
        will reveal A12b:
        - Concurrent writes from two regions within the lag window conflict
        - No vector clock or version tracking to detect/resolve conflicts
        - Last-write-wins causes silent data loss for concurrent updates
        """
        
        # In production, this should track lag and reject reads that are too stale
        logger.info(f"Syncing state from {source_region} to {target_region}")
        
        return True
