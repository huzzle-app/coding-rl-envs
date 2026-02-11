"""
SynapseNet Scheduler Service Views
Terminal Bench v2 - Job Scheduling & Cron Management

Contains bugs:
- L15: Worker registration needs scheduler service active
- K3: Feature flag evaluation race condition
"""
import time
import uuid
import threading
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class FeatureFlagManager:
    """
    Feature flag evaluation.

    BUG K3: Race condition when evaluating and updating flags simultaneously.
    A flag update may be partially visible during evaluation.
    """

    def __init__(self):
        self._flags: Dict[str, Dict[str, Any]] = {}
        

    def set_flag(self, flag_name: str, value: Any, rules: Optional[Dict] = None):
        """
        Set a feature flag.

        BUG K3: Not atomic - other threads may read partial state.
        """
        
        if flag_name not in self._flags:
            self._flags[flag_name] = {}
        self._flags[flag_name]["value"] = value
        
        if rules:
            self._flags[flag_name]["rules"] = rules
        self._flags[flag_name]["updated_at"] = time.time()

    def evaluate_flag(self, flag_name: str, context: Optional[Dict] = None) -> Any:
        """
        Evaluate a feature flag.

        BUG K3: May read inconsistent state during concurrent update.
        """
        flag = self._flags.get(flag_name)
        if not flag:
            return None
        return flag.get("value")


class WorkerRegistry:
    """
    Worker registration service.

    BUG L15: Workers try to register before scheduler is ready.
    """

    def __init__(self):
        self._workers: Dict[str, Dict[str, Any]] = {}
        self._is_ready = False

    def register_worker(self, worker_id: str, capabilities: List[str]) -> bool:
        """
        Register a worker.

        BUG L15: Does not wait for scheduler to be ready.
        """
        
        self._workers[worker_id] = {
            "capabilities": capabilities,
            "registered_at": time.time(),
            "status": "active",
            "last_heartbeat": time.time(),
        }
        return True

    def set_ready(self):
        """Mark scheduler as ready."""
        self._is_ready = True
