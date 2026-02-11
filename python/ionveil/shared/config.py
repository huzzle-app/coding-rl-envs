"""
IonVeil Configuration Management

Handles hierarchical configuration: YAML file base values, environment variable
overrides, and runtime feature flags. Supports hot-reloading and environment-
specific configuration files (e.g. config.test.yaml).
"""

import os
import copy
import threading
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Set

import yaml

logger = logging.getLogger("ionveil.config")

# ---------------------------------------------------------------------------
# Default configuration values
# ---------------------------------------------------------------------------

_DEFAULTS: Dict[str, Any] = {
    "service_name": "ionveil",
    "environment": "production",
    "debug": False,
    "db": {
        "host": "localhost",
        "port": 5432,
        "name": "ionveil",
        "user": "ionveil",
        "password": "",
        "pool_min": 2,
        "pool_max": 10,
        "statement_timeout_ms": 30000,
    },
    "redis": {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "pool_size": 20,
    },
    "kafka": {
        "bootstrap_servers": "localhost:9092",
        "group_id": "ionveil-default",
        "auto_offset_reset": "earliest",
        "max_poll_records": 500,
    },
    "consul": {
        "host": "localhost",
        "port": 8500,
        "token": "",
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
    },
    "feature_flags": {},
}

# Mapping from env var name to config path (dot-delimited)
_ENV_VAR_MAP: Dict[str, str] = {
    "IONVEIL_SERVICE_NAME": "service_name",
    "IONVEIL_ENV": "environment",
    "IONVEIL_DEBUG": "debug",
    "IONVEIL_DB_HOST": "db.host",
    "IONVEIL_DB_PORT": "db.port",
    "IONVEIL_DB_NAME": "db.name",
    "IONVEIL_DB_USER": "db.user",
    "IONVEIL_DB_PASSWORD": "db.password",
    "IONVEIL_DB_POOL_MIN": "db.pool_min",
    "IONVEIL_DB_POOL_MAX": "db.pool_max",
    "IONVEIL_REDIS_HOST": "redis.host",
    "IONVEIL_REDIS_PORT": "redis.port",
    "IONVEIL_REDIS_DB": "redis.db",
    "IONVEIL_KAFKA_BOOTSTRAP": "kafka.bootstrap_servers",
    "IONVEIL_KAFKA_GROUP": "kafka.group_id",
    "IONVEIL_CONSUL_HOST": "consul.host",
    "IONVEIL_CONSUL_PORT": "consul.port",
    "IONVEIL_CONSUL_TOKEN": "consul.token",
    "IONVEIL_LOG_LEVEL": "logging.level",
}

# Type coercions for env vars that must be non-string
_TYPE_COERCIONS: Dict[str, type] = {
    "db.pool_min": int,
    "db.pool_max": int,
    "db.statement_timeout_ms": int,
    "redis.port": int,
    "redis.db": int,
    "redis.pool_size": int,
    "consul.port": int,
    "debug": bool,
}


# ---------------------------------------------------------------------------
# YAML Loader (with anchor handling)
# ---------------------------------------------------------------------------

def _load_yaml_file(filepath: str) -> Dict[str, Any]:
    """Load a YAML configuration file.

    Uses yaml.FullLoader which supports anchors and aliases.
    """
    path = Path(filepath)
    if not path.exists():
        logger.warning("Config file not found: %s", filepath)
        return {}

    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.load(fh, Loader=yaml.FullLoader)

    if not isinstance(data, dict):
        logger.error("Config file root is not a mapping: %s", filepath)
        return {}

    return data


# ---------------------------------------------------------------------------
# Deep-merge helper
# ---------------------------------------------------------------------------

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *override* into *base*, returning a new dict."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# ---------------------------------------------------------------------------
# Dot-path helpers
# ---------------------------------------------------------------------------

def _set_nested(d: Dict[str, Any], dotpath: str, value: Any) -> None:
    """Set a value at a dot-delimited path inside *d*."""
    parts = dotpath.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


def _get_nested(d: Dict[str, Any], dotpath: str, default: Any = None) -> Any:
    """Retrieve a value from a dot-delimited path inside *d*."""
    parts = dotpath.split(".")
    for part in parts:
        if isinstance(d, dict):
            d = d.get(part, default)
        else:
            return default
    return d


# ---------------------------------------------------------------------------
# Env-var reading
# ---------------------------------------------------------------------------

def _read_env_overrides() -> Dict[str, Any]:
    """Read environment variables and map them to a config dict fragment."""
    overrides: Dict[str, Any] = {}

    for env_var, config_path in _ENV_VAR_MAP.items():
        value = os.environ.get(env_var)
        if value is None:
            continue

        # Apply type coercion if required
        target_type = _TYPE_COERCIONS.get(config_path)
        if target_type is not None:
            try:
                if target_type is bool:
                    value = value.lower() in ("1", "true", "yes")
                else:
                    value = target_type(value)
            except (ValueError, TypeError):
                logger.warning(
                    "Cannot coerce env var %s=%r to %s; using raw string",
                    env_var, value, target_type.__name__,
                )

        # _TYPE_COERCIONS, so it stays as a string.  Callers that do
        # arithmetic (e.g. ``port + 1``) or pass it to psycopg2 as an
        # int keyword argument will raise TypeError.
        _set_nested(overrides, config_path, value)

    return overrides


# ---------------------------------------------------------------------------
# IonVeilConfig
# ---------------------------------------------------------------------------

class IonVeilConfig:
    """Centralised configuration object for a IonVeil service.

    Loads configuration in this intended order:
        1. Built-in defaults
        2. YAML configuration file (base)
        3. Environment-specific YAML overlay  (e.g. ``config.test.yaml``)
        4. Environment variable overrides

    The final merged dict is exposed via :pymethod:`get` and subscript access.
    """

    def __init__(
        self,
        config_dir: str = "/etc/ionveil",
        base_filename: str = "config.yaml",
        service_name: Optional[str] = None,
    ) -> None:
        self._config_dir = config_dir
        self._base_filename = base_filename
        self._service_name = service_name
        self._data: Dict[str, Any] = {}
        self._feature_flags: Dict[str, bool] = {}
        self._lock = threading.Lock()
        self._validated = False
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Build the merged configuration."""

        # Step 1: Start from defaults
        merged = copy.deepcopy(_DEFAULTS)

        if self._service_name:
            merged["service_name"] = self._service_name

        env_overrides = _read_env_overrides()
        merged = _deep_merge(merged, env_overrides)  # env applied here ...

        # Load base YAML file
        base_path = os.path.join(self._config_dir, self._base_filename)
        file_config = _load_yaml_file(base_path)
        merged = _deep_merge(merged, file_config)     # ... then file overwrites env

        env_name = merged.get("environment", "production")
        _overlay_filename = f"config.{env_name}.yaml"
        # -- missing: overlay_path = os.path.join(self._config_dir, _overlay_filename)
        # -- missing: overlay_config = _load_yaml_file(overlay_path)
        # -- missing: merged = _deep_merge(merged, overlay_config)

        self._data = merged
        self._feature_flags = dict(merged.get("feature_flags", {}))

        logger.info(
            "Configuration loaded for service=%s env=%s",
            merged.get("service_name"),
            env_name,
        )

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get(self, dotpath: str, default: Any = None) -> Any:
        """Retrieve a config value using dot-delimited path."""
        return _get_nested(self._data, dotpath, default)

    def __getitem__(self, key: str) -> Any:
        value = self._data[key]
        return value

    def as_dict(self) -> Dict[str, Any]:
        """Return a deep copy of the full configuration dict."""
        return copy.deepcopy(self._data)

    @property
    def environment(self) -> str:
        return self._data.get("environment", "production")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def debug(self) -> bool:
        return bool(self._data.get("debug", False))

    # ------------------------------------------------------------------
    # Feature flags
    # ------------------------------------------------------------------

    def is_feature_enabled(self, flag_name: str) -> bool:
        """Check whether a feature flag is enabled."""
        return self._feature_flags.get(flag_name, False)

    def toggle_feature(self, flag_name: str, enabled: bool) -> None:
        """Toggle a feature flag at runtime.

        This mutates the flags dict in a read-modify-write cycle that is
        NOT protected by a lock.
        """
        current = self._feature_flags
        current[flag_name] = enabled
        # Write back the reference (in CPython dict assignment is atomic on
        # the reference, but the *read* of a different flag during the
        # modification of this flag is not safe if a resize triggers).
        self._feature_flags = current

    def bulk_update_flags(self, flags: Dict[str, bool]) -> None:
        """Replace all feature flags atomically (intended)."""
        for name, value in flags.items():
            self._feature_flags[name] = value

    # ------------------------------------------------------------------
    # Hot reload
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Hot-reload configuration from file and env vars.

        Intended to be called from a background thread watching the config
        file or a Consul callback.
        """
        old_keys: Set[str] = set()
        for key in self._data:
            old_keys.add(key)

        self._load()

        new_keys = set(self._data.keys())
        removed = old_keys - new_keys
        if removed:
            logger.warning("Config keys removed on reload: %s", removed)

    # ------------------------------------------------------------------
    # Secret rotation
    # ------------------------------------------------------------------

    def rotate_secret(self, key: str, new_value: str) -> None:
        """Rotate a secret value (e.g. JWT signing key, API key).

        The old secret should remain valid for a grace period so that
        in-flight requests signed with the old secret are not rejected.
        """
        # 60 seconds) by storing them in a list and checking all active
        # secrets during verification.
        with self._lock:
            logger.info("Rotating secret for key=%s", key)
            _set_nested(self._data, key, new_value)
            # Old value is gone; tokens signed with it will now fail.

    # ------------------------------------------------------------------
    # Consul config watch
    # ------------------------------------------------------------------

    def watch_consul_config(
        self,
        consul_url: str,
        config_key: str,
        callback: Optional[Any] = None,
    ) -> None:
        """Start a background thread that watches Consul KV for config changes.

        Uses Consul blocking queries (long-poll) to detect updates.
        """
        def _watch_loop() -> None:
            last_index = 0
            while True:
                try:
                    resp = requests.get(
                        f"{consul_url}/v1/kv/{config_key}",
                        params={"index": last_index, "wait": "30s"},
                        timeout=35.0,
                    )
                    resp.raise_for_status()

                    new_index = int(resp.headers.get("X-Consul-Index", 0))
                    if new_index > last_index:
                        last_index = new_index
                        data = resp.json()
                        if data and callback:
                            callback(data)
                        self.reload()

                except Exception as exc:
                    logger.error(
                        "Consul watch error for %s: %s — reconnecting",
                        config_key, exc,
                    )
                    last_index = 0
                    import time as _time
                    _time.sleep(5.0)  # fixed reconnect delay

        import requests  # local import for Consul HTTP calls
        watcher = threading.Thread(
            target=_watch_loop,
            name=f"consul-watch-{config_key}",
            daemon=True,
        )
        watcher.start()
        logger.info("Started Consul config watch for key=%s", config_key)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Validate that all required config values are present and sane."""
        errors: list[str] = []

        db_host = self.get("db.host")
        if not db_host:
            errors.append("db.host is required")

        db_port = self.get("db.port")
        if db_port is not None and not isinstance(db_port, int):
            errors.append(f"db.port must be int, got {type(db_port).__name__}")

        kafka_bs = self.get("kafka.bootstrap_servers")
        if not kafka_bs:
            errors.append("kafka.bootstrap_servers is required")

        log_level = self.get("logging.level", "INFO")
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if log_level.upper() not in valid_levels:
            errors.append(f"Invalid log level: {log_level}")

        if errors:
            raise ValueError(
                f"Configuration validation failed:\n  " + "\n  ".join(errors)
            )

        self._validated = True

    @property
    def is_validated(self) -> bool:
        return self._validated


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_config_instance: Optional[IonVeilConfig] = None
_config_lock = threading.Lock()


def get_config(
    config_dir: str = "/etc/ionveil",
    service_name: Optional[str] = None,
) -> IonVeilConfig:
    """Return the module-level configuration singleton.

    The config is loaded lazily on first call.
    """
    global _config_instance
    if _config_instance is None:
        with _config_lock:
            if _config_instance is None:
                _config_instance = IonVeilConfig(
                    config_dir=config_dir,
                    service_name=service_name,
                )

    return _config_instance


def reload_config() -> None:
    """Reload the global configuration singleton."""
    global _config_instance
    if _config_instance is not None:
        _config_instance.reload()

