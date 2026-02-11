"""Shared helpers.

This package intentionally avoids eager imports of optional dependencies.
"""

__all__ = []

try:
    from shared.config import IonVeilConfig, get_config, reload_config

    __all__ += ["IonVeilConfig", "get_config", "reload_config"]
except Exception:
    pass

try:
    from shared.clients import HttpClient, CircuitBreaker

    __all__ += ["HttpClient", "CircuitBreaker"]
except Exception:
    pass

try:
    from shared.kafka_client import KafkaProducer, KafkaConsumer

    __all__ += ["KafkaProducer", "KafkaConsumer"]
except Exception:
    pass

try:
    from shared.db import ConnectionPool, get_pool, execute_query

    __all__ += ["ConnectionPool", "get_pool", "execute_query"]
except Exception:
    pass
