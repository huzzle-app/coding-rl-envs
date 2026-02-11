"""
OmniCloud Tenants Service Models
Terminal Bench v2 - Tenant management with isolation.

Contains bugs:
- C1: Resource isolation bypass - missing tenant_id filter in queries
- C2: Quota enforcement race - concurrent requests exceed quota
- C3: Tenant scoping leak in raw SQL queries
- C4: Cross-tenant data access via shared cache key without tenant prefix
- C5: Tenant deletion leaves orphaned resources
- C6: Resource limit soft vs hard confusion
- C7: Tenant migration data loss - FK references not updated
- C8: Billing isolation miscalculation
"""
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class Tenant:
    """A tenant in the multi-cloud platform."""
    tenant_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    plan: str = "standard"
    is_active: bool = True
    created_at: float = field(default_factory=time.time)

    # Resource quotas
    max_compute_instances: int = 100
    max_storage_gb: int = 10000
    max_networks: int = 10
    max_load_balancers: int = 5

    # Current usage
    current_compute_instances: int = 0
    current_storage_gb: int = 0
    current_networks: int = 0
    current_load_balancers: int = 0


@dataclass
class TenantResourceStore:
    """Stores resources per tenant."""
    resources: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cache: Dict[str, Any] = field(default_factory=dict)

    def get_resources(self, tenant_id: str, resource_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get resources for a tenant.

        BUG C1: If tenant_id is None or empty, returns ALL resources across all tenants.
        Should reject queries without a valid tenant_id.
        """
        results = []
        for rid, resource in self.resources.items():
            
            if resource.get("tenant_id") == tenant_id:
                if resource_type is None or resource.get("type") == resource_type:
                    results.append(resource)
        return results

    def get_resource_by_id(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific resource by ID.

        BUG C1: No tenant_id check - any tenant can access any resource by ID.
        """
        
        return self.resources.get(resource_id)

    def check_quota(self, tenant: Tenant, resource_type: str, count: int = 1) -> bool:
        """Check if tenant has quota available.

        BUG C2: Not atomic - two concurrent requests can both pass the check
        and exceed the quota.
        """
        
        if resource_type == "compute_instance":
            return tenant.current_compute_instances + count <= tenant.max_compute_instances
        elif resource_type == "storage_gb":
            return tenant.current_storage_gb + count <= tenant.max_storage_gb
        elif resource_type == "network":
            return tenant.current_networks + count <= tenant.max_networks
        elif resource_type == "load_balancer":
            return tenant.current_load_balancers + count <= tenant.max_load_balancers
        return True

    def increment_usage(self, tenant: Tenant, resource_type: str, count: int = 1):
        """Increment tenant resource usage.

        BUG C2: Separate from check_quota - race condition between check and increment.
        """
        if resource_type == "compute_instance":
            tenant.current_compute_instances += count
        elif resource_type == "storage_gb":
            tenant.current_storage_gb += count

    def get_cached(self, key: str) -> Optional[Any]:
        """Get a value from cache.

        BUG C4: Cache keys don't include tenant_id prefix,
        allowing cross-tenant data access via shared cache.
        """
        
        return self.cache.get(key)

    def set_cached(self, key: str, value: Any):
        """Set a value in cache.

        BUG C4: Same issue - no tenant prefix in cache key.
        """
        self.cache[key] = value

    def delete_tenant_resources(self, tenant_id: str) -> int:
        """Delete all resources for a tenant.

        BUG C5: Only deletes from the resources dict, but doesn't clean up
        references in compute, network, storage, etc. services.
        """
        deleted = 0
        to_delete = [
            rid for rid, res in self.resources.items()
            if res.get("tenant_id") == tenant_id
        ]
        for rid in to_delete:
            del self.resources[rid]
            deleted += 1
        
        # to clean up their resources for this tenant
        return deleted

    def check_resource_limit(self, tenant: Tenant, resource_type: str, requested: int) -> bool:
        """Check if resource request is within limits.

        BUG C6: Treats soft limit as hard limit. Soft limits should allow
        temporary overages with warnings, not reject requests.
        """
        
        # Should differentiate: soft limit = warn, hard limit = reject
        return self.check_quota(tenant, resource_type, requested)

    def migrate_tenant(self, tenant_id: str, new_region: str) -> bool:
        """Migrate tenant resources to a new region.

        BUG C7: Updates resource region but doesn't update foreign key
        references (e.g., subnet -> VPC, instance -> security group).
        """
        for rid, resource in self.resources.items():
            if resource.get("tenant_id") == tenant_id:
                resource["region"] = new_region
                
                # e.g., subnet.vpc_id, instance.security_group_id
        return True

    def calculate_tenant_cost(
        self,
        tenant_id: str,
        shared_cost: Decimal,
        total_usage: Decimal,
        tenant_usage: Decimal,
    ) -> Decimal:
        """Calculate cost allocation for a tenant.

        BUG C8: Uses integer division for cost split, losing precision.
        """
        if total_usage == 0:
            return Decimal("0")

        ratio = float(tenant_usage) / float(total_usage)
        return Decimal(str(round(float(shared_cost) * ratio, 2)))

    def atomic_check_and_allocate(
        self,
        tenant: Tenant,
        resource_type: str,
        count: int = 1,
    ) -> bool:
        """Check quota and allocate resources for a tenant.

        Returns True if allocation succeeded, False if quota exceeded.
        """
        if not self.check_quota(tenant, resource_type, count):
            return False
        self.increment_usage(tenant, resource_type, count)
        return True

    def transfer_resources(
        self,
        source_tenant: Tenant,
        target_tenant: Tenant,
        resource_ids: List[str],
    ) -> int:
        """Transfer resources from one tenant to another.

        Re-assigns ownership and updates usage counters on both tenants.
        """
        transferred = 0
        for rid in resource_ids:
            resource = self.resources.get(rid)
            if resource and resource.get("tenant_id") == source_tenant.tenant_id:
                resource["tenant_id"] = target_tenant.tenant_id
                rtype = resource.get("type", "compute_instance")
                self.increment_usage(target_tenant, rtype)
                transferred += 1
        return transferred

    def deep_clone_tenant(self, tenant: Tenant) -> Tenant:
        """Create a deep clone of a tenant for testing/staging purposes.

        Produces a new tenant with copies of all associated resources.
        """
        clone = Tenant(
            name=f"{tenant.name}-clone",
            plan=tenant.plan,
            max_compute_instances=tenant.max_compute_instances,
            max_storage_gb=tenant.max_storage_gb,
            max_networks=tenant.max_networks,
            max_load_balancers=tenant.max_load_balancers,
        )
        cloned_resources = {}
        for rid, resource in self.resources.items():
            if resource.get("tenant_id") == tenant.tenant_id:
                new_rid = f"{rid}-clone"
                cloned_resources[new_rid] = dict(resource)
        for new_rid, res_copy in cloned_resources.items():
            res_copy["tenant_id"] = clone.tenant_id
            self.resources[new_rid] = res_copy
        return clone

    def calculate_resource_utilization(
        self,
        tenant: Tenant,
    ) -> Dict[str, float]:
        """Calculate resource utilization percentages for a tenant."""
        utilization = {}
        if tenant.max_compute_instances > 0:
            utilization["compute"] = (
                tenant.current_compute_instances / tenant.max_compute_instances
            )
        if tenant.max_storage_gb > 0:
            utilization["storage"] = (
                tenant.current_storage_gb / tenant.max_storage_gb
            )
        if tenant.max_networks > 0:
            utilization["network"] = (
                tenant.current_networks / tenant.max_networks
            )
        if tenant.max_load_balancers > 0:
            utilization["load_balancer"] = (
                tenant.current_load_balancers / tenant.max_load_balancers
            )
        return utilization
