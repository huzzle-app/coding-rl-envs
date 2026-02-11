"""Features service models."""


class FeatureGroup:
    """Feature group definition."""

    def __init__(self, name, entity_type, features=None):
        self.name = name
        self.entity_type = entity_type
        self.features = features or {}
        self.schema_version = 1
