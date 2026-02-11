"""Registry service models."""


class ModelVersion:
    """Model version in the registry."""

    def __init__(self, model_id, version, artifact_path, status="staged"):
        self.model_id = model_id
        self.version = version
        self.artifact_path = artifact_path
        self.status = status
        self.created_at = None
        self.promoted_at = None
