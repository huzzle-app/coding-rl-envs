"""Auth service models."""


class User:
    """User model for authentication."""

    def __init__(self, user_id, username, email, roles=None, tenant_id="default"):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.roles = roles or []
        self.tenant_id = tenant_id
        self.api_keys = []
        self.is_active = True


class APIKey:
    """API Key model."""

    def __init__(self, key_id, user_id, key_hash, expires_at=None):
        self.key_id = key_id
        self.user_id = user_id
        self.key_hash = key_hash
        self.expires_at = expires_at
        self.is_active = True
