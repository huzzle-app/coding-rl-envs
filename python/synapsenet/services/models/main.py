"""
SynapseNet Models Service
Terminal Bench v2 - Model CRUD & Metadata Management (FastAPI)

Contains bugs:
- I5: IDOR on model endpoints - no tenant check
- I7: Mass assignment on model update - all fields writable
"""
import os
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ModelMetadata:
    """Model metadata storage."""

    def __init__(self):
        self._models: Dict[str, Dict[str, Any]] = {}

    def create_model(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create a new model entry."""
        model_id = str(uuid.uuid4())
        model = {
            "model_id": model_id,
            "name": data.get("name", "unnamed"),
            "framework": data.get("framework", "unknown"),
            "version": data.get("version", "0.0.1"),
            "owner_id": user_id,
            "tenant_id": data.get("tenant_id", "default"),
            "input_schema": data.get("input_schema", {}),
            "output_schema": data.get("output_schema", {}),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "is_public": data.get("is_public", False),
            "status": "created",
        }
        self._models[model_id] = model
        return model

    def get_model(self, model_id: str, user_id: str = None, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Get a model by ID.

        BUG I5: Does not check tenant_id or owner_id. Any authenticated user
        can access any model by guessing the model_id (IDOR).
        """
        
        return self._models.get(model_id)

    def update_model(self, model_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update model metadata.

        BUG I7: Mass assignment - accepts all fields including owner_id, tenant_id,
        and is_public, allowing privilege escalation.
        """
        model = self._models.get(model_id)
        if not model:
            return None

        
        for key, value in updates.items():
            model[key] = value  # Should only allow specific fields

        model["updated_at"] = datetime.now(timezone.utc).isoformat()
        return model

    def list_models(self, tenant_id: str = None) -> List[Dict[str, Any]]:
        """List all models, optionally filtered by tenant."""
        if tenant_id:
            return [m for m in self._models.values() if m.get("tenant_id") == tenant_id]
        return list(self._models.values())

    def delete_model(self, model_id: str) -> bool:
        """Delete a model."""
        if model_id in self._models:
            del self._models[model_id]
            return True
        return False


model_store = ModelMetadata()

app = {
    "service": "models",
    "port": 8002,
    "store": model_store,
}
