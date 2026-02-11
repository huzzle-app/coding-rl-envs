"""
SynapseNet Worker Tasks
Terminal Bench v2 - Celery Worker Tasks

Distributed training tasks are defined in services/training/tasks.py
This module re-exports them for the worker process.
"""
import logging

logger = logging.getLogger(__name__)


def execute_training_step(job_id: str, batch_data: dict) -> dict:
    """Execute a training step on a worker."""
    return {"job_id": job_id, "status": "completed"}


def execute_data_pipeline_step(pipeline_id: str, step_id: str, data: dict) -> dict:
    """Execute a data pipeline step on a worker."""
    return {"pipeline_id": pipeline_id, "step_id": step_id, "status": "completed"}


def compute_features(entity_id: str, feature_group: str) -> dict:
    """Compute features for an entity."""
    return {"entity_id": entity_id, "feature_group": feature_group, "status": "completed"}
