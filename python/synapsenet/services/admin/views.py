"""
SynapseNet Admin Service Views
Terminal Bench v2 - Admin Dashboard & Tenant Management

Contains bugs:
- G6: mTLS certificate chain validation failure
- K4: Config reload not atomic
"""
import os
import time
import logging
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Configuration management with hot reload.

    BUG K4: Config reload is not atomic. During reload, a reader may
    see partially updated config (some keys from old, some from new).
    """

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._lock = threading.Lock()  

    def load_config(self, config: Dict[str, Any]):
        """
        Load configuration.

        BUG K4: Does not use lock during reload, allowing partial reads.
        """
        
        for key, value in config.items():
            self._config[key] = value  

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value."""
        return self._config.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """Get all config values."""
        return dict(self._config)


class CertificateValidator:
    """
    mTLS certificate validation.

    BUG G6: Does not validate the full certificate chain.
    Only checks if the leaf certificate is present, not the CA chain.
    """

    def __init__(self):
        self._trusted_cas: list = []

    def add_trusted_ca(self, ca_cert: str):
        """Add a trusted CA certificate."""
        self._trusted_cas.append(ca_cert)

    def validate_certificate(self, cert_chain: list) -> bool:
        """
        Validate a certificate chain.

        BUG G6: Only validates that a certificate is present,
        does not verify the chain back to a trusted CA.
        """
        if not cert_chain:
            return False

        
        leaf_cert = cert_chain[0]
        return bool(leaf_cert)  # Should verify chain against self._trusted_cas


class TenantManager:
    """Manage tenants."""

    def __init__(self):
        self._tenants: Dict[str, Dict[str, Any]] = {}

    def create_tenant(self, name: str, plan: str = "free") -> str:
        """Create a new tenant."""
        import uuid
        tenant_id = str(uuid.uuid4())
        self._tenants[tenant_id] = {
            "tenant_id": tenant_id,
            "name": name,
            "plan": plan,
            "is_active": True,
            "created_at": time.time(),
        }
        return tenant_id

    def get_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant by ID."""
        return self._tenants.get(tenant_id)
