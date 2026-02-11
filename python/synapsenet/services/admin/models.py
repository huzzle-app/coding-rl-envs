"""Admin service models."""


class Tenant:
    """Tenant model for multi-tenancy."""

    def __init__(self, tenant_id, name, plan="free"):
        self.tenant_id = tenant_id
        self.name = name
        self.plan = plan
        self.is_active = True
        self.settings = {}
