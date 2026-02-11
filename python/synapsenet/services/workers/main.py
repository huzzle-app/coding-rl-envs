"""
SynapseNet Workers Service
Terminal Bench v2 - Distributed Task Workers (Celery)

Contains bugs related to distributed training tasks.
See services/training/tasks.py for task implementations.
"""
import os
import logging

logger = logging.getLogger(__name__)


class WorkerManager:
    """Manage distributed workers."""

    def __init__(self):
        self._workers = {}

    def register(self, worker_id: str, capabilities: list):
        """Register a worker."""
        self._workers[worker_id] = {
            "capabilities": capabilities,
            "status": "idle",
        }

    def get_available_workers(self, capability: str = None) -> list:
        """Get available workers."""
        workers = []
        for wid, info in self._workers.items():
            if info["status"] == "idle":
                if capability is None or capability in info["capabilities"]:
                    workers.append(wid)
        return workers


app = {
    "service": "workers",
    "port": 8011,
}
