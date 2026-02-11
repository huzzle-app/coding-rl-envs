"""
SynapseNet Features Service Views
Terminal Bench v2 - Feature Store & Serving

Contains bugs:
- C1: Online/offline consistency (via shared.ml.feature_utils)
- C2: PIT join timezone (via shared.utils.time)
- C5: Feature backfill race condition
- C6: Feature schema evolution breaks backward compat
- C7: Feature serving cache stampede
- C8: Feature dependency graph cycle (via shared.ml.feature_utils)
"""
import time
import uuid
import logging
import threading
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class FeatureSchemaManager:
    """
    Manage feature schema evolution.

    BUG C6: Schema evolution does not check backward compatibility.
    Removing a field or changing its type breaks existing consumers.
    """

    def __init__(self):
        self._schemas: Dict[str, List[Dict[str, Any]]] = {}

    def register_schema(self, feature_group: str, schema: Dict[str, Any]) -> int:
        """
        Register a new schema version.

        BUG C6: Does not validate backward compatibility with previous version.
        """
        if feature_group not in self._schemas:
            self._schemas[feature_group] = []

        version = len(self._schemas[feature_group]) + 1
        
        # Should verify: all fields in previous version still exist with same types
        self._schemas[feature_group].append({
            "version": version,
            "schema": schema,
            "created_at": time.time(),
        })
        return version

    def get_schema(self, feature_group: str, version: int = -1) -> Optional[Dict[str, Any]]:
        """Get a schema version."""
        schemas = self._schemas.get(feature_group, [])
        if not schemas:
            return None
        if version == -1:
            return schemas[-1]
        if 0 < version <= len(schemas):
            return schemas[version - 1]
        return None


class BackfillManager:
    """
    Manage feature backfill operations.

    BUG C5: Race condition when two backfill jobs run simultaneously
    for the same feature group. Both may process the same entities.
    """

    def __init__(self):
        self._active_backfills: Dict[str, Dict[str, Any]] = {}
        

    def start_backfill(self, feature_group: str, entity_ids: List[str]) -> str:
        """
        Start a backfill job.

        BUG C5: Does not check for existing backfill on same feature group.
        """
        backfill_id = str(uuid.uuid4())
        
        self._active_backfills[backfill_id] = {
            "feature_group": feature_group,
            "entity_ids": entity_ids,
            "processed": [],
            "status": "running",
            "started_at": time.time(),
        }
        return backfill_id

    def process_entity(self, backfill_id: str, entity_id: str) -> bool:
        """Process a single entity in a backfill."""
        if backfill_id not in self._active_backfills:
            return False
        backfill = self._active_backfills[backfill_id]
        
        backfill["processed"].append(entity_id)
        return True


class FeatureCacheManager:
    """
    Feature serving cache with stampede protection.

    BUG C7: Missing stampede protection. When a popular feature expires,
    all concurrent requests hit the backend simultaneously.
    """

    def __init__(self, ttl: float = 60.0):
        self.ttl = ttl
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        """
        Get a cached feature value.

        BUG C7: No stampede protection - all requests hit backend on expiry.
        """
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["cached_at"] < self.ttl:
                return entry["value"]
            
            del self._cache[key]
        return None

    def set(self, key: str, value: Any):
        """Set a cache entry."""
        self._cache[key] = {
            "value": value,
            "cached_at": time.time(),
        }
