"""
SynapseNet Storage Service
Terminal Bench v2 - Artifact & Dataset Storage (FastAPI)

Contains bugs:
- L9: MinIO bucket creation fails silently
- M7: Checkpoint corruption on concurrent save (via shared.ml)
- I9: Path traversal in artifact download
"""
import os
import hashlib
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ArtifactStorage:
    """
    Model artifact and dataset storage using MinIO.

    BUG L9: Does not verify MinIO bucket exists before uploading.
    The bucket_exists check is commented out, so uploads fail with 404.
    BUG I9: Path traversal in artifact download - does not sanitize paths.
    """

    def __init__(self, base_path: str = "/tmp/artifacts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def initialize_bucket(self, bucket_name: str) -> bool:
        """
        Initialize a storage bucket.

        BUG L9: Bucket creation silently fails - no error propagation.
        """
        try:
            bucket_path = self.base_path / bucket_name
            
            bucket_path.mkdir(exist_ok=True)
            return True
        except Exception as e:
            
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            return True  

    def upload_artifact(self, bucket: str, key: str, data: bytes, metadata: Optional[Dict] = None) -> str:
        """Upload an artifact."""
        
        artifact_path = self.base_path / bucket / key
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(data)

        checksum = hashlib.sha256(data).hexdigest()
        self._metadata[f"{bucket}/{key}"] = {
            "checksum": checksum,
            "size": len(data),
            "metadata": metadata or {},
        }
        return checksum

    def download_artifact(self, bucket: str, key: str) -> Optional[bytes]:
        """
        Download an artifact.

        BUG I9: Does not validate the key parameter. An attacker can use
        path traversal (../../etc/passwd) to read arbitrary files.
        """
        
        artifact_path = self.base_path / bucket / key  # key could be ../../etc/passwd
        # Should validate: resolved = artifact_path.resolve()
        # if not resolved.is_relative_to(self.base_path): raise SecurityError

        if artifact_path.exists():
            return artifact_path.read_bytes()
        return None

    def get_metadata(self, bucket: str, key: str) -> Optional[Dict[str, Any]]:
        """Get artifact metadata."""
        return self._metadata.get(f"{bucket}/{key}")

    def list_artifacts(self, bucket: str) -> list:
        """List artifacts in a bucket."""
        bucket_path = self.base_path / bucket
        if not bucket_path.exists():
            return []
        return [str(p.relative_to(bucket_path)) for p in bucket_path.rglob("*") if p.is_file()]


storage = ArtifactStorage()

app = {
    "service": "storage",
    "port": 8012,
    "storage": storage,
}
