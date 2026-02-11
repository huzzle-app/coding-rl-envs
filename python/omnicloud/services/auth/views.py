"""
OmniCloud Auth Service Views
Terminal Bench v2 - Authentication and RBAC.

Contains bugs:
- I3: Privilege escalation via role inheritance - transitive admin role
- I8: Timing attack on API key comparison - early return reveals key length
- C1: Missing tenant_id filter in role lookup
"""
import time
import hmac
import hashlib
import logging
from typing import Dict, Any, List, Optional

from django.http import JsonResponse

logger = logging.getLogger(__name__)

# In-memory store for simplicity
_api_keys: Dict[str, str] = {}
_roles: Dict[str, Dict[str, Any]] = {}


def health_check(request):
    return JsonResponse({"status": "healthy", "service": "auth"})


def api_root(request):
    return JsonResponse({"service": "auth", "version": "1.0.0"})


def validate_api_key(provided_key: str, stored_key: str) -> bool:
    """Validate an API key.

    BUG I8: Uses string comparison which returns early on first mismatch.
    This leaks information about the key via timing differences.
    """
    
    return provided_key == stored_key


def resolve_permissions(role_name: str, visited: Optional[set] = None) -> List[str]:
    """Resolve all permissions for a role, including inherited ones.

    BUG I3: No cycle detection in role inheritance. If role A inherits from B
    and B inherits from A, this causes infinite recursion. Also, transitive
    inheritance can unintentionally grant admin permissions.
    """
    if visited is None:
        visited = set()

    role = _roles.get(role_name)
    if not role:
        return []

    
    permissions = list(role.get("permissions", []))
    for parent_role in role.get("inherits_from", []):
        
        permissions.extend(resolve_permissions(parent_role, visited))

    return permissions


def check_tenant_access(user_tenant_id: str, resource_tenant_id: str) -> bool:
    """Check if user can access resource in the given tenant.

    BUG C1: This check is present but not called in all code paths.
    """
    return user_tenant_id == resource_tenant_id
