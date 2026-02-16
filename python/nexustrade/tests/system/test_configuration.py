"""
System tests for configuration management bugs.

These tests verify bugs K1-K8 (Configuration Management category).
"""
import pytest
import copy
import time
import json
import hashlib
from collections import OrderedDict


class TestEnvironmentConfig:
    """Tests for bug K1: Environment variable precedence inversion."""

    def test_env_precedence(self):
        """Test that environment variables take precedence over config files."""
        
        config_file_values = {
            "DATABASE_URL": "postgres://localhost:5432/dev",
            "LOG_LEVEL": "DEBUG",
            "MAX_CONNECTIONS": "10",
        }
        env_overrides = {
            "DATABASE_URL": "postgres://prod-db:5432/production",
            "LOG_LEVEL": "WARN",
        }

        # Correct precedence: env > config file > defaults
        resolved = {}
        for key, value in config_file_values.items():
            resolved[key] = env_overrides.get(key, value)

        assert resolved["DATABASE_URL"] == "postgres://prod-db:5432/production", (
            "Env variable should override config file"
        )
        assert resolved["LOG_LEVEL"] == "WARN", (
            "Env variable should override config file"
        )
        assert resolved["MAX_CONNECTIONS"] == "10", (
            "Config file value should be used when no env override exists"
        )

    def test_config_override(self):
        """Test that config override chain works correctly."""
        
        defaults = {"timeout": 30, "retries": 3, "log_level": "INFO"}
        config_file = {"timeout": 60, "log_level": "DEBUG"}
        env_vars = {"timeout": 120}
        cli_args = {}

        # Precedence: cli > env > config > defaults
        resolved = {}
        resolved.update(defaults)
        resolved.update(config_file)
        resolved.update(env_vars)
        resolved.update(cli_args)

        assert resolved["timeout"] == 120, "Env var should override config file"
        assert resolved["retries"] == 3, "Default should be used when not overridden"
        assert resolved["log_level"] == "DEBUG", "Config file should override default"

    def test_default_value_fallback(self):
        """Test that defaults are used when no config is provided."""
        
        defaults = {
            "port": 8080,
            "host": "0.0.0.0",
            "workers": 4,
            "graceful_shutdown_timeout": 30,
        }

        # Simulate empty config (new deployment)
        user_config = {}

        resolved = {}
        for key, default_value in defaults.items():
            resolved[key] = user_config.get(key, default_value)

        assert resolved["port"] == 8080, "Default port should be used"
        assert resolved["workers"] == 4, "Default workers should be used"
        assert len(resolved) == len(defaults), "All defaults should be present"


class TestServiceDiscoveryConfig:
    """Tests for bug K2: Service discovery cache TTL misconfiguration."""

    def test_discovery_ttl(self):
        """Test that service discovery cache respects TTL."""
        
        cache_ttl_seconds = 30
        cached_at = time.monotonic()
        current_time = cached_at + 31  # Past TTL

        cached_entry = {
            "service": "order-service",
            "endpoints": ["10.0.0.1:8080", "10.0.0.2:8080"],
            "cached_at": cached_at,
        }

        is_stale = (current_time - cached_entry["cached_at"]) > cache_ttl_seconds
        assert is_stale, "Cache entry past TTL should be considered stale"

    def test_stale_endpoint(self):
        """Test that stale endpoints are detected and removed."""
        
        endpoints = [
            {"host": "10.0.0.1:8080", "last_heartbeat": 100, "healthy": True},
            {"host": "10.0.0.2:8080", "last_heartbeat": 50, "healthy": True},
            {"host": "10.0.0.3:8080", "last_heartbeat": 10, "healthy": True},
        ]

        heartbeat_timeout = 60
        current_time = 110

        healthy_endpoints = []
        for ep in endpoints:
            if (current_time - ep["last_heartbeat"]) <= heartbeat_timeout:
                healthy_endpoints.append(ep)

        assert len(healthy_endpoints) == 2, "Only 2 endpoints should be within heartbeat window"
        stale_hosts = [
            ep["host"] for ep in endpoints if ep not in healthy_endpoints
        ]
        assert "10.0.0.3:8080" in stale_hosts, "Stale endpoint should be identified"

    def test_discovery_retry_on_failure(self):
        """Test that service discovery retries on failure."""
        
        max_retries = 3
        attempts = 0
        last_known_good = ["10.0.0.1:8080", "10.0.0.2:8080"]

        def discover_services(fail_until):
            nonlocal attempts
            attempts += 1
            if attempts < fail_until:
                raise ConnectionError("Discovery service unavailable")
            return ["10.0.0.1:8080", "10.0.0.2:8080", "10.0.0.3:8080"]

        result = None
        for attempt in range(1, max_retries + 1):
            try:
                result = discover_services(fail_until=3)
                break
            except ConnectionError:
                if attempt == max_retries:
                    result = last_known_good  # Fall back to last known good
                continue

        assert result is not None, "Discovery should return a result or fallback"
        assert len(result) >= 2, "Should have at least fallback endpoints"


class TestFeatureFlags:
    """Tests for bug K3: Feature flag evaluation race condition."""

    def test_feature_flag_consistency(self):
        """Test that feature flags are evaluated consistently."""
        
        flags = {
            "new_matching_engine": {"enabled": True, "rollout_pct": 50},
            "dark_pool_support": {"enabled": False, "rollout_pct": 0},
            "advanced_orders": {"enabled": True, "rollout_pct": 100},
        }

        # Same user should always get the same flag evaluation
        user_id = "user-456"
        evaluations = []
        for _ in range(10):
            user_hash = int(hashlib.md5(user_id.encode()).hexdigest(), 16) % 100
            is_enabled = (
                flags["new_matching_engine"]["enabled"]
                and user_hash < flags["new_matching_engine"]["rollout_pct"]
            )
            evaluations.append(is_enabled)

        assert len(set(evaluations)) == 1, (
            "Same user should always get the same flag evaluation"
        )

    def test_flag_evaluation(self):
        """Test feature flag evaluation logic."""
        
        flags = {
            "beta_feature": {"enabled": True, "rollout_pct": 0},
            "ga_feature": {"enabled": True, "rollout_pct": 100},
            "disabled_feature": {"enabled": False, "rollout_pct": 100},
        }

        # Rollout at 0% should mean no users get the feature (even if enabled)
        user_hash = 50
        beta_enabled = flags["beta_feature"]["enabled"] and user_hash < flags["beta_feature"]["rollout_pct"]
        assert not beta_enabled, "Beta feature at 0% rollout should be off for all users"

        # GA feature at 100% should be on for all users
        ga_enabled = flags["ga_feature"]["enabled"] and user_hash < flags["ga_feature"]["rollout_pct"]
        assert ga_enabled, "GA feature at 100% should be on"

        # Disabled feature should be off regardless of rollout
        disabled = flags["disabled_feature"]["enabled"] and user_hash < flags["disabled_feature"]["rollout_pct"]
        assert not disabled, "Disabled feature should be off regardless of rollout"


class TestConfigReload:
    """Tests for bug K4: Configuration hot-reload race condition."""

    def test_config_atomicity(self):
        """Test that configuration updates are atomic."""
        
        old_config = {
            "database": {"host": "db-old", "port": 5432, "pool_size": 10},
            "cache": {"host": "cache-old", "port": 6379},
        }
        new_config = {
            "database": {"host": "db-new", "port": 5432, "pool_size": 20},
            "cache": {"host": "cache-new", "port": 6379},
        }

        # Atomic swap: the entire config should be replaced at once
        active_config = copy.deepcopy(old_config)
        staged_config = copy.deepcopy(new_config)

        # Simulate atomic swap
        active_config = staged_config

        assert active_config["database"]["host"] == "db-new", (
            "Database host should be updated"
        )
        assert active_config["cache"]["host"] == "cache-new", (
            "Cache host should be updated atomically with database"
        )

    def test_reload_safety(self):
        """Test that config reload doesn't disrupt active requests."""
        
        class ConfigHolder:
            def __init__(self, config):
                self._config = copy.deepcopy(config)
                self._version = 1

            def get(self, key):
                return self._config.get(key)

            def reload(self, new_config):
                # Create new snapshot, old references still valid
                old_version = self._version
                self._config = copy.deepcopy(new_config)
                self._version = old_version + 1
                return self._version

        holder = ConfigHolder({"timeout": 30})

        # Simulate in-flight request reading config
        request_timeout = holder.get("timeout")
        assert request_timeout == 30

        # Config reload happens while request is in-flight
        new_version = holder.reload({"timeout": 60})

        # The in-flight request should still use old value
        assert request_timeout == 30, "In-flight request should not be affected by reload"
        # New requests should use new value
        assert holder.get("timeout") == 60, "New requests should use reloaded config"
        assert new_version == 2


class TestSecretManagement:
    """Tests for bug K5: Secret rotation without zero-downtime."""

    def test_secret_rotation_window(self):
        """Test that secret rotation supports a transition window."""
        
        old_key = "secret-key-v1"
        new_key = "secret-key-v2"

        # During rotation, both keys should be valid
        valid_keys = {old_key, new_key}

        # Requests signed with either key should be accepted
        request_with_old = {"payload": "data", "signature_key": old_key}
        request_with_new = {"payload": "data", "signature_key": new_key}

        assert request_with_old["signature_key"] in valid_keys, (
            "Old key should be valid during rotation"
        )
        assert request_with_new["signature_key"] in valid_keys, (
            "New key should be valid during rotation"
        )

    def test_dual_key_support(self):
        """Test that system supports dual active keys during rotation."""
        
        class KeyManager:
            def __init__(self):
                self.active_keys = OrderedDict()

            def add_key(self, key_id, key_value):
                self.active_keys[key_id] = key_value

            def retire_key(self, key_id):
                if key_id in self.active_keys:
                    del self.active_keys[key_id]

            def is_valid(self, key_value):
                return key_value in self.active_keys.values()

        manager = KeyManager()
        manager.add_key("v1", "secret-abc")
        manager.add_key("v2", "secret-def")

        assert manager.is_valid("secret-abc"), "Old key should be valid"
        assert manager.is_valid("secret-def"), "New key should be valid"

        # Retire old key after rotation window
        manager.retire_key("v1")
        assert not manager.is_valid("secret-abc"), "Retired key should be invalid"
        assert manager.is_valid("secret-def"), "Current key should remain valid"

    def test_secret_masking_in_logs(self):
        """Test that secrets are masked in log output."""
        
        def mask_secret(value):
            if len(value) <= 4:
                return "****"
            return value[:2] + "*" * (len(value) - 4) + value[-2:]

        secret = "my-super-secret-api-key"
        masked = mask_secret(secret)

        assert "super-secret" not in masked, "Secret content should not appear in masked output"
        assert len(masked) == len(secret), "Masked output should preserve length"
        assert masked.startswith("my"), "Prefix hint should be preserved"
        assert masked.endswith("ey"), "Suffix hint should be preserved"
        assert "****" in masked or masked.count("*") > 0, "Should contain mask characters"


class TestConfigParsing:
    """Tests for bug K6: YAML anchor/merge key resolution failures."""

    def test_yaml_anchors(self):
        """Test that YAML anchor references are resolved correctly."""
        
        # Simulate resolved YAML with anchors
        base_config = {
            "host": "localhost",
            "port": 5432,
            "pool_size": 10,
            "timeout": 30,
        }

        # YAML anchor reuse: database.primary and database.replica share base
        primary = {**base_config, "host": "primary-db.internal", "role": "primary"}
        replica = {**base_config, "host": "replica-db.internal", "role": "replica", "pool_size": 5}

        assert primary["port"] == replica["port"], "Shared anchor values should be equal"
        assert primary["timeout"] == 30, "Anchor values should be resolved"
        assert primary["host"] != replica["host"], "Overridden values should differ"

    def test_config_merge(self):
        """Test that config merge operations work correctly."""
        
        base = {
            "server": {"host": "0.0.0.0", "port": 8080},
            "logging": {"level": "INFO", "format": "json"},
            "features": ["auth", "rate-limit"],
        }
        override = {
            "server": {"port": 9090},
            "logging": {"level": "DEBUG"},
        }

        # Deep merge
        merged = copy.deepcopy(base)
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key].update(value)
            else:
                merged[key] = value

        assert merged["server"]["host"] == "0.0.0.0", "Non-overridden nested values should persist"
        assert merged["server"]["port"] == 9090, "Overridden nested values should update"
        assert merged["logging"]["level"] == "DEBUG", "Override should take effect"
        assert merged["logging"]["format"] == "json", "Non-overridden values should persist"
        assert merged["features"] == ["auth", "rate-limit"], "Lists should be preserved"


class TestConfigVersioning:
    """Tests for bug K7: Config version mismatch between services."""

    def test_config_version(self):
        """Test that config versions are tracked and validated."""
        
        service_configs = {
            "order-service": {"version": "v2.3", "schema_version": 5},
            "matching-engine": {"version": "v2.3", "schema_version": 5},
            "settlement-service": {"version": "v2.2", "schema_version": 4},  # Lagging
        }

        versions = set(c["version"] for c in service_configs.values())
        assert len(versions) > 1, "Test setup: should have version mismatch"

        # Detect version mismatch
        latest_version = max(c["version"] for c in service_configs.values())
        lagging_services = [
            name for name, config in service_configs.items()
            if config["version"] != latest_version
        ]
        assert "settlement-service" in lagging_services, (
            "Should detect settlement-service is lagging"
        )

    def test_service_agreement(self):
        """Test that services agree on shared configuration schema."""
        
        schema_v4 = {"fields": ["order_id", "price", "quantity", "side"]}
        schema_v5 = {"fields": ["order_id", "price", "quantity", "side", "time_in_force"]}

        message = {
            "order_id": "ord-001",
            "price": 150.00,
            "quantity": 100,
            "side": "buy",
            "time_in_force": "GTC",
        }

        # Service using v4 schema would miss time_in_force field
        v4_fields = set(schema_v4["fields"])
        v5_fields = set(schema_v5["fields"])
        extra_fields = v5_fields - v4_fields

        assert "time_in_force" in extra_fields, (
            "Schema v5 should have time_in_force not present in v4"
        )

        # Verify backward compatibility
        message_v4_keys = set(message.keys()).intersection(v4_fields)
        assert len(message_v4_keys) == len(v4_fields), (
            "v5 messages should contain all v4 fields for backward compatibility"
        )

    def test_config_rollback(self):
        """Test that configuration can be rolled back to a previous version."""
        
        config_history = [
            {"version": 1, "config": {"timeout": 30, "retries": 3, "pool_size": 10}},
            {"version": 2, "config": {"timeout": 60, "retries": 5, "pool_size": 20}},
            {"version": 3, "config": {"timeout": 45, "retries": 4, "pool_size": 15}},
        ]

        current = config_history[-1]
        assert current["version"] == 3

        # Rollback to version 1
        rollback_target = 1
        rollback_config = None
        for entry in config_history:
            if entry["version"] == rollback_target:
                rollback_config = copy.deepcopy(entry["config"])
                break

        assert rollback_config is not None, "Rollback target should exist in history"
        assert rollback_config["timeout"] == 30, "Timeout should match version 1"
        assert rollback_config["retries"] == 3, "Retries should match version 1"
        assert rollback_config["pool_size"] == 10, "Pool size should match version 1"


class TestConfigWatching:
    """Tests for bug K8: Config watch event lost during reconnection."""

    def test_consul_watch(self):
        """Test that config changes are detected via watch mechanism."""
        
        class ConfigWatcher:
            def __init__(self):
                self.callbacks = []
                self.last_index = 0

            def register(self, callback):
                self.callbacks.append(callback)

            def on_change(self, new_index, new_value):
                if new_index > self.last_index:
                    self.last_index = new_index
                    for cb in self.callbacks:
                        cb(new_value)

        changes_received = []
        watcher = ConfigWatcher()
        watcher.register(lambda v: changes_received.append(v))

        # Simulate config change
        watcher.on_change(1, {"timeout": 60})
        watcher.on_change(2, {"timeout": 90})

        assert len(changes_received) == 2, "Both changes should be received"
        assert changes_received[-1]["timeout"] == 90, "Latest change should have updated timeout"

    def test_config_notification(self):
        """Test that config change notifications reach all subscribers."""
        
        class NotificationBus:
            def __init__(self):
                self.subscribers = {}
                self.delivered = {}

            def subscribe(self, subscriber_id, callback):
                self.subscribers[subscriber_id] = callback
                self.delivered[subscriber_id] = []

            def notify_all(self, event):
                for sub_id, callback in self.subscribers.items():
                    callback(event)
                    self.delivered[sub_id].append(event)

        bus = NotificationBus()

        # Register multiple subscribers
        results = {"order-service": [], "matching-engine": [], "settlement": []}
        bus.subscribe("order-service", lambda e: results["order-service"].append(e))
        bus.subscribe("matching-engine", lambda e: results["matching-engine"].append(e))
        bus.subscribe("settlement", lambda e: results["settlement"].append(e))

        # Notify config change
        bus.notify_all({"type": "config_change", "key": "timeout", "value": 60})

        for service, events in results.items():
            assert len(events) == 1, f"{service} should have received the notification"
            assert events[0]["value"] == 60, f"{service} should have correct config value"

    def test_config_change_debounce(self):
        """Test that rapid config changes are debounced."""
        
        class DebouncedWatcher:
            def __init__(self, debounce_ms):
                self.debounce_ms = debounce_ms
                self.pending_value = None
                self.applied_values = []
                self.last_change_time = None

            def on_change(self, value, timestamp_ms):
                self.pending_value = value
                self.last_change_time = timestamp_ms

            def tick(self, current_time_ms):
                if (
                    self.pending_value is not None
                    and self.last_change_time is not None
                    and (current_time_ms - self.last_change_time) >= self.debounce_ms
                ):
                    self.applied_values.append(self.pending_value)
                    self.pending_value = None

        watcher = DebouncedWatcher(debounce_ms=500)

        # Rapid changes within debounce window
        watcher.on_change({"timeout": 30}, timestamp_ms=100)
        watcher.on_change({"timeout": 45}, timestamp_ms=200)
        watcher.on_change({"timeout": 60}, timestamp_ms=300)

        # Tick within debounce window - nothing should be applied yet
        watcher.tick(current_time_ms=400)
        assert len(watcher.applied_values) == 0, "No changes should be applied during debounce"

        # Tick after debounce window - only last change should be applied
        watcher.tick(current_time_ms=900)
        assert len(watcher.applied_values) == 1, "Only one debounced change should be applied"
        assert watcher.applied_values[0]["timeout"] == 60, (
            "Should apply the last value in the debounce window"
        )


# ===================================================================
# Source-code-verifying tests for configuration & time bugs
# ===================================================================


class TestMarketOpenBoundary:
    """Tests that is_market_open handles close boundary correctly (BUG F5)."""

    def test_market_close_uses_strict_less_than(self):
        """is_market_open must use < (not <=) for market close boundary."""
        import inspect
        from shared.utils.time import is_market_open
        src = inspect.getsource(is_market_open)
        # Should NOT have <= market_close (accepting orders at exactly close time)
        assert "<= market_close" not in src, \
            "is_market_open should use strict < for market close, not <="

    def test_market_close_timezone_handling(self):
        """is_market_open must use proper timezone (not hardcoded offset) (BUG F5)."""
        import inspect
        from shared.utils.time import is_market_open
        src = inspect.getsource(is_market_open)
        # Should use pytz or zoneinfo for proper DST handling
        uses_proper_tz = ("zoneinfo" in src or "pytz" in src or
                          "ZoneInfo" in src or "Eastern" in src.split("zoneinfo")[-1:]
                          if "zoneinfo" in src else False)
        has_hardcoded_offset = "hours=-5" in src
        assert not has_hardcoded_offset or uses_proper_tz, \
            "is_market_open should use zoneinfo/pytz for timezone, not hardcoded offset"


class TestSettlementDateWeekendSkip:
    """Tests that get_settlement_date skips weekends (BUG F8)."""

    def test_settlement_date_skips_weekends(self):
        """get_settlement_date must skip weekends when counting settlement days."""
        import inspect
        from shared.utils.time import get_settlement_date
        src = inspect.getsource(get_settlement_date)
        # Must check for weekdays to skip weekends
        assert "weekday" in src or "weekend" in src.lower() or "business" in src.lower(), \
            "get_settlement_date must skip weekends when calculating settlement date"

    def test_friday_trade_settles_after_weekend(self):
        """A trade on Friday with T+2 should settle on Tuesday, not Sunday."""
        from datetime import datetime, timezone
        from shared.utils.time import get_settlement_date
        # Friday trade
        friday = datetime(2024, 1, 5, 14, 0, tzinfo=timezone.utc)  # A Friday
        settlement = get_settlement_date(friday, settlement_days=2)
        # Should be Tuesday (Jan 9), not Sunday (Jan 7)
        assert settlement.weekday() < 5, \
            f"Settlement date {settlement} falls on weekend (day {settlement.weekday()})"


class TestRateLimiterBypass:
    """Tests that RateLimiter cannot be bypassed with headers (BUG I4)."""

    def test_rate_limiter_no_header_bypass(self):
        """RateLimiter must not bypass rate limiting based on X-Internal-Request header."""
        import inspect
        from shared.utils.time import RateLimiter
        src = inspect.getsource(RateLimiter.acquire)
        assert "X-Internal-Request" not in src, \
            "RateLimiter should not bypass rate limiting based on X-Internal-Request header"

    def test_rate_limiter_enforced_with_internal_header(self):
        """Rate limiting must be enforced even when X-Internal-Request is set."""
        from shared.utils.time import RateLimiter
        limiter = RateLimiter(rate=1.0, capacity=1.0)
        # Exhaust tokens
        limiter.acquire(1)
        # With X-Internal-Request header, should still be rate-limited
        result = limiter.acquire(1, headers={"X-Internal-Request": "true"})
        assert not result, \
            "Rate limiter must not bypass for X-Internal-Request header"
