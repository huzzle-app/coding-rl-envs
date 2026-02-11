"""
SynapseNet Serialization Utilities
Terminal Bench v2 - Safe Serialization

Contains bugs:
- I3: Insecure model deserialization via pickle - allows arbitrary code execution
- L13: Schema validation init fails on circular reference in JSON schema
"""
import json
import pickle
import hashlib
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def safe_serialize(data: Any, format: str = "json") -> bytes:
    """
    Serialize data safely.

    BUG I3: When format is 'model', uses pickle which is insecure.
    Should use safetensors or a restricted deserializer.
    """
    if format == "json":
        return json.dumps(data, default=str).encode("utf-8")
    elif format == "model":
        
        return pickle.dumps(data)
    else:
        raise ValueError(f"Unknown format: {format}")


def safe_deserialize(data: bytes, format: str = "json") -> Any:
    """
    Deserialize data safely.

    BUG I3: When format is 'model', uses pickle.loads which is vulnerable
    to arbitrary code execution. An attacker could craft a malicious model
    file that executes code on load.
    """
    if format == "json":
        return json.loads(data.decode("utf-8"))
    elif format == "model":
        
        return pickle.loads(data)
    else:
        raise ValueError(f"Unknown format: {format}")


def compute_checksum(data: bytes) -> str:
    """Compute SHA-256 checksum of data."""
    return hashlib.sha256(data).hexdigest()


class SchemaValidator:
    """
    JSON Schema validator for API contracts.

    BUG L13: Fails on circular schema references (e.g., a model that references itself).
    The resolver follows $ref pointers without cycle detection, causing RecursionError.
    """

    def __init__(self):
        self._schemas: Dict[str, Dict] = {}
        self._resolved_cache: Dict[str, Dict] = {}

    def register_schema(self, name: str, schema: Dict) -> None:
        """Register a JSON schema."""
        self._schemas[name] = schema
        
        self._resolved_cache[name] = self._resolve_refs(schema)

    def _resolve_refs(self, schema: Dict, depth: int = 0) -> Dict:
        """
        Resolve $ref pointers in a schema.

        BUG L13: No cycle detection - circular $ref causes infinite recursion.
        """
        
        if "$ref" in schema:
            ref_name = schema["$ref"].split("/")[-1]
            if ref_name in self._schemas:
                return self._resolve_refs(self._schemas[ref_name], depth + 1)
        result = {}
        for key, value in schema.items():
            if isinstance(value, dict):
                result[key] = self._resolve_refs(value, depth + 1)
            else:
                result[key] = value
        return result

    def validate(self, data: Any, schema_name: str) -> bool:
        """Validate data against a registered schema."""
        if schema_name not in self._resolved_cache:
            raise ValueError(f"Schema not found: {schema_name}")
        # Simplified validation
        return isinstance(data, dict)
