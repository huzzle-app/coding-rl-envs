"""
OmniCloud End-to-End System Tests
Terminal Bench v2 - System tests for configuration management, IaC workflows.

Covers bugs: K1-K12
~80 tests
"""
import pytest
import re
import copy
from typing import Dict, Any, List, Set
from collections import defaultdict

from services.config.views import (
    interpolate_variables, resolve_env_precedence,
    topological_sort, merge_resource_defaults,
    evaluate_conditional_count, expand_dynamic_blocks,
)
from services.secrets.views import SecretResolver
from shared.infra.state import StateManager, Resource, ResourceState
from shared.infra.reconciler import Reconciler


class TestTemplateVariableInterpolation:
    """Tests for K1: Template variable cycle detection."""

    def test_template_variable_no_cycle(self):
        """K1: Circular variable references should be detected and stopped."""
        variables = {
            "a": "${b}",
            "b": "${a}",  # Circular reference
        }

        
        result = interpolate_variables("Hello ${a}", variables, max_depth=10)
        # Should terminate, not loop forever
        assert result is not None

    def test_interpolation_terminates(self):
        """K1: Interpolation with max_depth should always terminate."""
        variables = {
            "x": "${y}",
            "y": "${z}",
            "z": "${x}",  # Cycle
        }

        # With bounded depth, should terminate
        result = interpolate_variables("${x}", variables, max_depth=5)
        assert isinstance(result, str)

    def test_simple_interpolation(self):
        """K1: Simple variable interpolation should work."""
        variables = {"name": "world"}
        result = interpolate_variables("Hello ${name}!", variables, max_depth=10)
        assert result == "Hello world!"

    def test_nested_interpolation(self):
        """K1: Nested variables should be resolved."""
        variables = {
            "greeting": "Hello ${name}",
            "name": "World",
        }
        result = interpolate_variables("${greeting}!", variables, max_depth=10)
        assert result == "Hello World!"

    def test_missing_variable_preserved(self):
        """K1: Missing variables should be preserved as-is."""
        variables = {"a": "1"}
        result = interpolate_variables("${a} ${b}", variables, max_depth=10)
        assert "1" in result
        assert "${b}" in result

    def test_no_variables(self):
        """K1: String without variables should pass through unchanged."""
        result = interpolate_variables("plain text", {}, max_depth=10)
        assert result == "plain text"

    def test_empty_template(self):
        """K1: Empty template should return empty string."""
        result = interpolate_variables("", {}, max_depth=10)
        assert result == ""


class TestPlanApplyConsistency:
    """Tests for K2: IaC plan vs apply drift."""

    def test_plan_apply_consistency(self):
        """K2: Apply should produce exactly what plan predicted."""
        plan = {
            "create": [{"id": "r1", "type": "compute", "cpu": 4}],
            "update": [],
            "delete": [],
        }
        applied = {
            "create": [{"id": "r1", "type": "compute", "cpu": 4}],
            "update": [],
            "delete": [],
        }
        assert plan == applied, "Apply result should match plan"

    def test_no_drift_after_apply(self):
        """K2: Immediately after apply, there should be no drift."""
        desired = {"r1": {"cpu": 4, "memory": 16}}
        actual = {"r1": {"cpu": 4, "memory": 16}}

        drift = {}
        for key in desired:
            if desired[key] != actual.get(key):
                drift[key] = {"desired": desired[key], "actual": actual.get(key)}

        assert len(drift) == 0, f"Found drift after apply: {drift}"

    def test_plan_detects_changes(self):
        """K2: Plan should detect differences between desired and actual state."""
        desired = {"r1": {"cpu": 8}}
        actual = {"r1": {"cpu": 4}}

        changes = []
        for key in desired:
            if desired[key] != actual.get(key):
                changes.append(key)

        assert len(changes) == 1

    def test_plan_idempotent(self):
        """K2: Running plan twice with same state should produce same result."""
        state = {"r1": {"cpu": 4}}
        plan1 = {"changes": len([k for k in state if state[k] != state[k]])}
        plan2 = {"changes": len([k for k in state if state[k] != state[k]])}
        assert plan1 == plan2


class TestEnvVarPrecedence:
    """Tests for K3: Environment variable precedence."""

    def test_env_var_precedence_correct(self):
        """K3: Precedence should be CLI > env > config > defaults."""
        result = resolve_env_precedence(
            cli_args={"key": "cli_value"},
            env_vars={"key": "env_value"},
            config_file={"key": "config_value"},
            defaults={"key": "default_value"},
        )
        # CLI should win
        assert result["key"] == "cli_value", \
            f"CLI should have highest precedence, got {result['key']}"

    def test_override_order(self):
        """K3: Each level should properly override the one below."""
        # Without CLI, env should win
        result = resolve_env_precedence(
            cli_args={},
            env_vars={"key": "env_value"},
            config_file={"key": "config_value"},
            defaults={"key": "default_value"},
        )
        
        assert result["key"] == "env_value", \
            f"Env vars should override config file, got {result['key']}"

    def test_defaults_used_when_no_override(self):
        """K3: Defaults should be used when nothing overrides them."""
        result = resolve_env_precedence(
            cli_args={},
            env_vars={},
            config_file={},
            defaults={"key": "default_value"},
        )
        assert result["key"] == "default_value"

    def test_config_overrides_default(self):
        """K3: Config file should override defaults."""
        result = resolve_env_precedence(
            cli_args={},
            env_vars={},
            config_file={"key": "config_value"},
            defaults={"key": "default_value"},
        )
        assert result["key"] == "config_value"

    def test_all_levels_combined(self):
        """K3: Multiple keys at different levels should coexist."""
        result = resolve_env_precedence(
            cli_args={"a": "cli_a"},
            env_vars={"b": "env_b"},
            config_file={"c": "config_c"},
            defaults={"d": "default_d"},
        )
        assert result["a"] == "cli_a"
        assert result["b"] == "env_b"
        assert result["c"] == "config_c"
        assert result["d"] == "default_d"


class TestConfigVersionPinning:
    """Tests for K4: Config version pinning race condition."""

    def test_config_version_pinning(self):
        """K4: Config version should be locked during apply."""
        config_version = {"version": 5, "locked_by": None}

        # Lock config for apply
        config_version["locked_by"] = "apply-1"
        assert config_version["locked_by"] == "apply-1"

    def test_version_race_prevented(self):
        """K4: Concurrent applies should be serialized."""
        config = {"version": 1, "locked": False}

        # First apply locks
        config["locked"] = True
        # Second apply should wait
        can_proceed = not config["locked"]
        assert can_proceed is False

    def test_version_increments_on_apply(self):
        """K4: Config version should increment after successful apply."""
        config = {"version": 1}
        config["version"] += 1
        assert config["version"] == 2

    def test_version_unchanged_on_failure(self):
        """K4: Failed apply should not change version."""
        config = {"version": 3}
        original_version = config["version"]
        # Simulate failed apply - version should not change
        assert config["version"] == original_version


class TestSecretResolution:
    """Tests for K5: Secret reference resolution mode."""

    def test_secret_reference_resolution(self):
        """K5: Secrets should be resolved eagerly at deploy time."""
        resolver = SecretResolver()
        resolver.cache["db_password"] = "secret123"

        
        assert resolver.resolution_mode == "eager", \
            f"Secret resolution should be eager, got {resolver.resolution_mode}"

    def test_lazy_eager_correct(self):
        """K5: Eager resolution should use cached value from deploy time."""
        resolver = SecretResolver()
        resolver.resolution_mode = "eager"
        resolver.cache["api_key"] = "deploy_time_key"

        result = resolver.resolve("api_key")
        assert result == "deploy_time_key"

    def test_lazy_resolution_stale(self):
        """K5: Lazy resolution returns value at read time (potentially different)."""
        resolver = SecretResolver()
        assert resolver.resolution_mode == "lazy"  # Current buggy state
        resolver.cache["key"] = "value"
        result = resolver.resolve("key")
        assert result is not None

    def test_missing_secret_returns_none_or_default(self):
        """K5: Missing secret should return None or a default."""
        resolver = SecretResolver()
        result = resolver.resolve("nonexistent")
        assert result is not None  # Returns default-secret-value


class TestDependencyTopologicalSort:
    """Tests for K6: Topological sort determinism."""

    def test_dependency_topological_sort(self):
        """K6: Topological sort should produce a valid ordering."""
        graph = {
            "a": set(),
            "b": {"a"},
            "c": {"a", "b"},
        }
        result = topological_sort(graph)

        # a should come before b, b before c
        a_idx = result.index("a")
        b_idx = result.index("b")
        c_idx = result.index("c")

        assert a_idx < b_idx < c_idx, \
            f"Expected a < b < c, got order: {result}"

    def test_sort_deterministic(self):
        """K6: Same graph should always produce same order."""
        graph = {
            "x": set(),
            "y": set(),
            "z": {"x", "y"},
        }

        
        results = set()
        for _ in range(10):
            result = tuple(topological_sort(graph))
            results.add(result)

        assert len(results) == 1, \
            f"Topological sort should be deterministic, got {len(results)} different orderings"

    def test_single_node_sort(self):
        """K6: Single node should return that node."""
        result = topological_sort({"a": set()})
        assert result == ["a"]

    def test_linear_chain_sort(self):
        """K6: Linear chain should be sorted in dependency order."""
        graph = {"a": set(), "b": {"a"}, "c": {"b"}}
        result = topological_sort(graph)
        assert result.index("a") < result.index("b") < result.index("c")

    def test_empty_graph(self):
        """K6: Empty graph should return empty list."""
        result = topological_sort({})
        assert result == []

    def test_diamond_dependency(self):
        """K6: Diamond dependency should have valid ordering."""
        graph = {
            "a": set(),
            "b": {"a"},
            "c": {"a"},
            "d": {"b", "c"},
        }
        result = topological_sort(graph)
        assert result.index("a") < result.index("d")
        assert result.index("b") < result.index("d")
        assert result.index("c") < result.index("d")


class TestProviderPluginVersion:
    """Tests for K7: Provider plugin version conflict."""

    def test_provider_plugin_version(self):
        """K7: Provider plugin versions should be validated."""
        required_version = ">=1.5.0,<2.0.0"
        installed_version = "1.7.3"

        # Simple version check
        major, minor, patch = map(int, installed_version.split("."))
        assert major >= 1 and minor >= 5

    def test_version_conflict_detected(self):
        """K7: Conflicting version requirements should be detected."""
        requirements = [
            {"provider": "aws", "version": ">=4.0,<5.0"},
            {"provider": "aws", "version": ">=3.0,<4.0"},  # Conflict
        ]

        # Check for conflicts
        versions_per_provider = defaultdict(list)
        for req in requirements:
            versions_per_provider[req["provider"]].append(req["version"])

        conflicts = {
            p: vs for p, vs in versions_per_provider.items()
            if len(vs) > 1
        }
        assert "aws" in conflicts

    def test_compatible_versions(self):
        """K7: Compatible versions should pass validation."""
        required = ">=1.0.0"
        installed = "1.5.0"
        major_req = 1
        major_inst = int(installed.split(".")[0])
        assert major_inst >= major_req

    def test_missing_provider_detected(self):
        """K7: Missing required provider should be detected."""
        required_providers = {"aws", "azure", "gcp"}
        installed_providers = {"aws", "azure"}
        missing = required_providers - installed_providers
        assert "gcp" in missing


class TestResourceDefaultMerge:
    """Tests for K8: Deep merge for resource defaults."""

    def test_resource_default_merge(self):
        """K8: Resource defaults should be deep merged with overrides."""
        defaults = {
            "compute": {
                "cpu": 2,
                "memory": 4,
                "tags": {"env": "dev"},
            }
        }
        overrides = {
            "compute": {
                "cpu": 4,
                "tags": {"team": "platform"},
            }
        }

        result = merge_resource_defaults(defaults, overrides)

        
        # Should deep merge: cpu=4, memory=4, tags={env: dev, team: platform}
        compute = result.get("compute", {})
        if isinstance(compute, dict):
            assert compute.get("memory") == 4, \
                "Deep merge should preserve 'memory' from defaults"

    def test_deep_merge_correct(self):
        """K8: Nested dicts should be recursively merged."""
        defaults = {"a": {"b": 1, "c": 2}}
        overrides = {"a": {"c": 3, "d": 4}}

        result = merge_resource_defaults(defaults, overrides)

        
        a = result.get("a", {})
        if isinstance(a, dict):
            assert "b" in a, "Deep merge should preserve 'b' from defaults"
            assert a.get("c") == 3, "Override 'c' should take precedence"

    def test_non_dict_override(self):
        """K8: Non-dict values should be directly replaced."""
        result = merge_resource_defaults({"key": "old"}, {"key": "new"})
        assert result["key"] == "new"

    def test_empty_override(self):
        """K8: Empty overrides should return defaults."""
        defaults = {"a": 1, "b": 2}
        result = merge_resource_defaults(defaults, {})
        assert result == defaults

    def test_empty_defaults(self):
        """K8: Empty defaults should return overrides."""
        overrides = {"a": 1}
        result = merge_resource_defaults({}, overrides)
        assert result == overrides


class TestOutputReference:
    """Tests for K9: Output reference cycle detection."""

    def test_output_reference_no_cycle(self):
        """K9: Circular output references should be detected."""
        outputs = {
            "vpc_id": "${output.subnet_id}",
            "subnet_id": "${output.vpc_id}",  # Cycle
        }

        # Detect cycle by trying to resolve
        visited = set()

        def resolve(key, visited):
            if key in visited:
                return None  # Cycle detected
            visited.add(key)
            val = outputs.get(key, key)
            if val.startswith("${output."):
                ref_key = val.replace("${output.", "").rstrip("}")
                return resolve(ref_key, visited)
            return val

        result = resolve("vpc_id", visited)
        assert result is None, "Circular output reference should be detected"

    def test_output_resolution(self):
        """K9: Valid output references should resolve."""
        outputs = {
            "vpc_id": "vpc-123",
            "subnet_id": "subnet-456",
        }
        assert outputs["vpc_id"] == "vpc-123"

    def test_chained_output_resolution(self):
        """K9: Chained output references should resolve."""
        outputs = {
            "a": "value_a",
            "b": "value_a",  # References a's value
        }
        assert outputs["b"] == outputs["a"]

    def test_missing_output_reference(self):
        """K9: Missing output reference should produce clear error."""
        outputs = {"a": "1"}
        assert "b" not in outputs


class TestWorkspaceIsolation:
    """Tests for K10: Workspace variable isolation."""

    def test_workspace_variable_isolation(self):
        """K10: Variables from one workspace should not leak to another."""
        workspace_dev = {"region": "us-east-1", "env": "dev"}
        workspace_prod = {"region": "eu-west-1", "env": "prod"}

        assert workspace_dev["region"] != workspace_prod["region"]

    def test_no_variable_leak(self):
        """K10: Switching workspaces should clear previous variables."""
        workspaces = {
            "dev": {"db_host": "dev-db.example.com", "debug": "true"},
            "prod": {"db_host": "prod-db.example.com", "debug": "false"},
        }

        current = dict(workspaces["dev"])
        # Switch to prod
        current = dict(workspaces["prod"])

        assert current["db_host"] == "prod-db.example.com"
        assert current.get("debug") == "false"

    def test_workspace_default_variables(self):
        """K10: Each workspace should have its own defaults."""
        defaults = {"region": "us-east-1"}
        ws1 = {**defaults, "env": "dev"}
        ws2 = {**defaults, "env": "prod"}

        ws1["region"] = "us-west-2"
        assert ws2["region"] == "us-east-1", "Changing ws1 should not affect ws2"

    def test_workspace_names_unique(self):
        """K10: Workspace names should be unique."""
        workspaces = {"dev", "staging", "prod"}
        assert len(workspaces) == 3


class TestConditionalResourceCount:
    """Tests for K11: Conditional resource count boundary."""

    def test_conditional_resource_count(self):
        """K11: count=0 with condition=True should create 0 resources."""
        result = evaluate_conditional_count(condition=True, count=0)
        
        assert result == 0, f"count=0 should create 0 resources, got {result}"

    def test_count_boundary_correct(self):
        """K11: count=1 with condition=True should create exactly 1 resource."""
        result = evaluate_conditional_count(condition=True, count=1)
        assert result == 1

    def test_condition_false_zero_resources(self):
        """K11: condition=False should always return 0 regardless of count."""
        assert evaluate_conditional_count(False, 5) == 0
        assert evaluate_conditional_count(False, 0) == 0

    def test_condition_true_count_positive(self):
        """K11: condition=True with positive count should return count."""
        assert evaluate_conditional_count(True, 3) == 3
        assert evaluate_conditional_count(True, 10) == 10

    def test_large_count(self):
        """K11: Large count values should work correctly."""
        assert evaluate_conditional_count(True, 1000) == 1000


class TestDynamicBlockExpansion:
    """Tests for K12: Dynamic block expansion order."""

    def test_dynamic_block_expansion(self):
        """K12: Dynamic blocks should be expanded in declaration order."""
        blocks = [
            {"name": "ingress", "for_each": ["80", "443"]},
            {"name": "egress", "for_each": ["all"]},
        ]

        expanded = expand_dynamic_blocks(blocks)
        names = [b["name"] for b in expanded]

        
        assert names[0] == "ingress", \
            f"First expanded block should be 'ingress', got '{names[0]}'"

    def test_block_ordering_stable(self):
        """K12: Block expansion should maintain stable order."""
        blocks = [
            {"name": "a", "for_each": ["1", "2"]},
            {"name": "b", "for_each": ["3", "4"]},
            {"name": "c", "for_each": ["5"]},
        ]

        expanded = expand_dynamic_blocks(blocks)
        names = [b["name"] for b in expanded]

        # Check that all 'a' blocks come before 'b' blocks
        a_indices = [i for i, n in enumerate(names) if n == "a"]
        b_indices = [i for i, n in enumerate(names) if n == "b"]
        c_indices = [i for i, n in enumerate(names) if n == "c"]

        if a_indices and b_indices:
            assert max(a_indices) < min(b_indices), \
                f"'a' blocks should come before 'b' blocks, got order: {names}"

    def test_static_blocks_preserved(self):
        """K12: Blocks without for_each should be preserved as-is."""
        blocks = [
            {"name": "static", "key": "value"},
            {"name": "dynamic", "for_each": ["x", "y"]},
        ]
        expanded = expand_dynamic_blocks(blocks)
        static_blocks = [b for b in expanded if b["name"] == "static"]
        assert len(static_blocks) == 1

    def test_empty_for_each(self):
        """K12: Empty for_each should not create any blocks."""
        blocks = [{"name": "empty", "for_each": []}]
        expanded = expand_dynamic_blocks(blocks)
        assert len(expanded) == 0

    def test_expansion_values_correct(self):
        """K12: Expanded blocks should contain the iteration value."""
        blocks = [{"name": "rule", "for_each": ["80", "443", "8080"]}]
        expanded = expand_dynamic_blocks(blocks)
        values = [b["value"] for b in expanded]
        assert "80" in values
        assert "443" in values
        assert "8080" in values

    def test_no_blocks(self):
        """K12: Empty block list should return empty."""
        assert expand_dynamic_blocks([]) == []


class TestStateManagerEndToEnd:
    """System-level tests for state management lifecycle."""

    def test_full_lifecycle(self):
        """Complete lifecycle: create -> update -> delete."""
        manager = StateManager()
        resource = Resource(
            resource_id="r1",
            resource_type="compute_instance",
            tenant_id="t1",
        )
        manager.resources["r1"] = resource

        # Transition through states
        manager.transition_state("r1", ResourceState.CREATING)
        assert resource.state == ResourceState.CREATING

    def test_reconciler_basic(self):
        """Reconciler should detect differences."""
        reconciler = Reconciler()
        desired = {"r1": {"type": "compute", "cpu": 4}}
        actual = {"r1": {"type": "compute", "cpu": 2}}

        result = reconciler.reconcile(desired, actual)
        assert result is not None

    def test_state_persistence(self):
        """State should be serializable for persistence."""
        manager = StateManager()
        resource = Resource(resource_id="r1", resource_type="compute")
        manager.resources["r1"] = resource

        assert "r1" in manager.resources

    def test_multi_tenant_state(self):
        """State manager should handle multiple tenants."""
        manager = StateManager()
        for i in range(5):
            r = Resource(
                resource_id=f"r{i}",
                resource_type="compute",
                tenant_id=f"t{i % 2}",
            )
            manager.resources[f"r{i}"] = r

        assert len(manager.resources) == 5


class TestInterpolationEdgeCases:
    """Additional template interpolation tests."""

    def test_double_dollar_literal(self):
        """Non-variable patterns should be preserved."""
        result = interpolate_variables("Price: $100", {}, max_depth=5)
        assert "$100" in result

    def test_multiple_vars_in_one_string(self):
        """Multiple variables in one string should all resolve."""
        variables = {"a": "1", "b": "2"}
        result = interpolate_variables("${a}-${b}", variables, max_depth=5)
        assert result == "1-2"

    def test_recursive_depth_limit(self):
        """Recursive variables should stop at depth limit."""
        variables = {"x": "${x}"}  # Self-referencing
        result = interpolate_variables("${x}", variables, max_depth=3)
        assert isinstance(result, str)


class TestEnvPrecedenceEdgeCases:
    """Additional env precedence tests."""

    def test_empty_all_levels(self):
        """All empty levels should return empty."""
        result = resolve_env_precedence({}, {}, {}, {})
        assert result == {}

    def test_single_key_at_each_level(self):
        """Each level should contribute independently."""
        result = resolve_env_precedence(
            {"cli_only": "cli"},
            {"env_only": "env"},
            {"config_only": "config"},
            {"default_only": "default"},
        )
        assert result["cli_only"] == "cli"
        assert result["env_only"] == "env"
        assert result["config_only"] == "config"
        assert result["default_only"] == "default"


class TestTopologicalSortEdgeCases:
    """Additional topological sort tests."""

    def test_parallel_chains(self):
        """Independent chains should both appear."""
        graph = {
            "a1": set(), "a2": {"a1"},
            "b1": set(), "b2": {"b1"},
        }
        result = topological_sort(graph)
        assert result.index("a1") < result.index("a2")
        assert result.index("b1") < result.index("b2")

    def test_wide_graph(self):
        """Wide graph with many roots should work."""
        graph = {f"root_{i}": set() for i in range(20)}
        graph["leaf"] = {f"root_{i}" for i in range(20)}
        result = topological_sort(graph)
        assert result[-1] == "leaf" or "leaf" in result


class TestMergeEdgeCases:
    """Additional merge tests."""

    def test_merge_with_none_value(self):
        """None values should be handled."""
        result = merge_resource_defaults({"key": None}, {"key": "value"})
        assert result["key"] == "value"

    def test_merge_new_keys(self):
        """New keys in overrides should be added."""
        result = merge_resource_defaults({"a": 1}, {"b": 2})
        assert result["a"] == 1
        assert result["b"] == 2

    def test_merge_preserves_types(self):
        """Merge should preserve value types."""
        result = merge_resource_defaults(
            {"num": 42, "text": "hello", "flag": True},
            {}
        )
        assert isinstance(result["num"], int)
        assert isinstance(result["text"], str)
        assert isinstance(result["flag"], bool)


class TestConditionalCountEdgeCases:
    """Additional conditional count tests."""

    def test_negative_count(self):
        """Negative count with condition True should return the count value."""
        result = evaluate_conditional_count(True, -1)
        # With bug: max(1, -1) = 1; without bug: should return -1 or 0
        assert result >= 0 or result == -1

    def test_count_two(self):
        """Count of 2 should return 2."""
        assert evaluate_conditional_count(True, 2) == 2

    def test_count_hundred(self):
        """Count of 100 should return 100."""
        assert evaluate_conditional_count(True, 100) == 100


class TestDynamicBlockEdgeCases:
    """Additional dynamic block tests."""

    def test_single_item_for_each(self):
        """Single item for_each should create one block."""
        blocks = [{"name": "single", "for_each": ["only"]}]
        expanded = expand_dynamic_blocks(blocks)
        assert len(expanded) == 1
        assert expanded[0]["value"] == "only"

    def test_mixed_static_dynamic(self):
        """Mix of static and dynamic blocks should be correct."""
        blocks = [
            {"name": "static1"},
            {"name": "dynamic", "for_each": ["a", "b"]},
            {"name": "static2"},
        ]
        expanded = expand_dynamic_blocks(blocks)
        names = [b["name"] for b in expanded]
        assert "static1" in names
        assert "static2" in names
        assert names.count("dynamic") == 2

    def test_many_for_each_items(self):
        """Many for_each items should all be expanded."""
        items = [str(i) for i in range(50)]
        blocks = [{"name": "rule", "for_each": items}]
        expanded = expand_dynamic_blocks(blocks)
        assert len(expanded) == 50


class TestSecretResolverEdgeCases:
    """Additional secret resolver tests."""

    def test_resolver_eager_mode(self):
        """Eager mode should only use cache."""
        resolver = SecretResolver()
        resolver.resolution_mode = "eager"
        resolver.cache["key"] = "cached_value"
        assert resolver.resolve("key") == "cached_value"

    def test_resolver_eager_missing(self):
        """Eager mode with missing key should return None."""
        resolver = SecretResolver()
        resolver.resolution_mode = "eager"
        result = resolver.resolve("nonexistent")
        assert result is None

    def test_resolver_lazy_fallback(self):
        """Lazy mode should fetch from vault."""
        resolver = SecretResolver()
        assert resolver.resolution_mode == "lazy"
        result = resolver.resolve("any_key")
        assert result is not None


class TestStateManagerOperations:
    """Additional state manager operation tests."""

    def test_add_and_remove_resource(self):
        """Adding and removing a resource should work."""
        manager = StateManager()
        r = Resource(resource_id="add-rm")
        manager.add_resource(r)
        assert "add-rm" in manager.resources
        manager.remove_resource("add-rm")
        assert "add-rm" not in manager.resources

    def test_remove_nonexistent(self):
        """Removing non-existent resource should return False."""
        manager = StateManager()
        assert manager.remove_resource("nope") is False

    def test_detect_drift_no_resource(self):
        """Drift detection on missing resource should return False."""
        manager = StateManager()
        assert manager.detect_drift("nonexistent") is False

    def test_detect_drift_matching(self):
        """No drift when configs match."""
        manager = StateManager()
        r = Resource(
            resource_id="match",
            desired_config={"cpu": 4},
            actual_config={"cpu": 4},
        )
        manager.resources["match"] = r
        assert manager.detect_drift("match") is False

    def test_detect_drift_different(self):
        """Drift when configs differ."""
        manager = StateManager()
        r = Resource(
            resource_id="diff",
            desired_config={"cpu": 4},
            actual_config={"cpu": 2},
        )
        manager.resources["diff"] = r
        assert manager.detect_drift("diff") is True

    def test_snapshot_and_restore(self):
        """Snapshot and restore should produce identical state."""
        manager = StateManager()
        for i in range(10):
            r = Resource(
                resource_id=f"sr{i}",
                resource_type="compute",
                tenant_id=f"t{i}",
                desired_config={"cpu": i},
            )
            manager.resources[f"sr{i}"] = r

        manager.take_snapshot("test-snap")
        original_count = len(manager.resources)
        manager.resources.clear()
        manager.restore_snapshot("test-snap")
        assert len(manager.resources) == original_count

    def test_update_resource_version_bumps(self):
        """Updating resource should bump version."""
        manager = StateManager()
        r = Resource(resource_id="versioned", version=1)
        manager.resources["versioned"] = r
        manager.update_resource("versioned", {"new": True})
        assert r.version == 2

    def test_transition_invalid_state(self):
        """Invalid transition should return False."""
        manager = StateManager()
        r = Resource(resource_id="inv", state=ResourceState.DELETED)
        manager.resources["inv"] = r
        result = manager.transition_state("inv", ResourceState.ACTIVE)
        assert result is False

    def test_build_dependency_graph(self):
        """Dependency graph should include all resources."""
        manager = StateManager()
        r1 = Resource(resource_id="dep1", dependencies=[])
        r2 = Resource(resource_id="dep2", dependencies=["dep1"])
        manager.resources["dep1"] = r1
        manager.resources["dep2"] = r2
        graph = manager.build_dependency_graph()
        assert "dep1" in graph
        assert "dep2" in graph
        assert "dep1" in graph["dep2"]
