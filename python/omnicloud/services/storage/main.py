"""
OmniCloud Storage Service
Terminal Bench v2 - Block and object storage provisioning.

Contains bugs:
- A7: Partial apply rollback incomplete (via shared reconciler)
- I6: Path traversal in artifact download
"""
import os
import uuid
import logging
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="OmniCloud Storage", version="1.0.0")

ARTIFACT_BASE_DIR = "/app/artifacts"


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "storage"}


@app.post("/api/v1/volumes")
async def create_volume(data: Dict[str, Any]):
    """Create a block storage volume."""
    return {"volume_id": str(uuid.uuid4()), "status": "creating"}


@app.get("/api/v1/volumes/{volume_id}")
async def get_volume(volume_id: str):
    """Get volume details."""
    return {"volume_id": volume_id, "status": "active"}


@app.post("/api/v1/buckets")
async def create_bucket(data: Dict[str, Any]):
    """Create an object storage bucket."""
    return {"bucket_id": str(uuid.uuid4()), "status": "creating"}


@app.get("/api/v1/artifacts/{artifact_path:path}")
async def download_artifact(artifact_path: str):
    """Download an artifact from storage.

    BUG I6: Path traversal vulnerability - artifact_path is not sanitized.
    An attacker can use ../../etc/passwd to escape the artifact directory.
    """
    
    full_path = os.path.join(ARTIFACT_BASE_DIR, artifact_path)
    # Should verify: os.path.realpath(full_path).startswith(os.path.realpath(ARTIFACT_BASE_DIR))

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(full_path)
