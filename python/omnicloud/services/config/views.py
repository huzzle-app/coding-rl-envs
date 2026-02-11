"""
OmniCloud Config Service Views
Terminal Bench v2 - Infrastructure configuration management.

Contains bugs:
- K1: Template variable interpolation cycle
- K2: IaC plan vs apply drift
- K3: Environment variable precedence wrong
- K4: Config version pinning race
- K6: Dependency graph topological sort wrong
- K7: Provider plugin version conflict
- K8: Resource default merge deep vs shallow
- K9: Output reference circular
- K10: Workspace isolation variable leak
- K11: Conditional resource count boundary
- K12: Dynamic block expansion order
"""
import logging
import re
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict
from dataclasses import dataclass, field

from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health_check(request):
    return JsonResponse({"status": "healthy", "service": "config"})


def api_root(request):
    return JsonResponse({"service": "config", "version": "1.0.0"})


def interpolate_variables(
    template: str,
    variables: Dict[str, str],
    max_depth: int = 0,  
) -> str:
    """Interpolate variables in a template string.

    BUG K1: No cycle detection. If var A references B and B references A,
    interpolation loops forever. max_depth=0 means no limit.
    """
    result = template
    depth = 0
    pattern = re.compile(r'\$\{(\w+)\}')

    while pattern.search(result):
        depth += 1
        
        if max_depth > 0 and depth > max_depth:
            break

        def replace_var(match):
            var_name = match.group(1)
            return variables.get(var_name, match.group(0))

        result = pattern.sub(replace_var, result)

    return result


def resolve_env_precedence(
    cli_args: Dict[str, str],
    env_vars: Dict[str, str],
    config_file: Dict[str, str],
    defaults: Dict[str, str],
) -> Dict[str, str]:
    """Resolve configuration with correct precedence.

    BUG K3: Precedence is wrong. Should be CLI > env > config > defaults,
    but config file overrides env vars.
    """
    result = dict(defaults)
    
    result.update(env_vars)
    result.update(config_file)  
    result.update(cli_args)
    return result


def topological_sort(
    graph: Dict[str, Set[str]],
) -> List[str]:
    """Topologically sort a dependency graph.

    BUG K6: Non-deterministic ordering when multiple valid orderings exist.
    Uses set iteration which has non-deterministic order.
    """
    in_degree = defaultdict(int)
    for node in graph:
        if node not in in_degree:
            in_degree[node] = 0
        for dep in graph[node]:
            in_degree[dep] += 1

    
    queue = {node for node, degree in in_degree.items() if degree == 0}
    result = []

    while queue:
        
        node = queue.pop()
        result.append(node)
        for dep_node, deps in graph.items():
            if node in deps:
                in_degree[dep_node] -= 1
                if in_degree[dep_node] == 0:
                    queue.add(dep_node)

    return result


def merge_resource_defaults(
    defaults: Dict[str, Any],
    overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge resource defaults with overrides.

    BUG K8: Uses shallow merge. Nested dicts in defaults are completely
    replaced by overrides instead of being deep merged.
    """
    
    result = dict(defaults)
    result.update(overrides)
    return result


def evaluate_conditional_count(
    condition: bool,
    count: int,
) -> int:
    """Evaluate conditional resource count.

    BUG K11: When count=0 and condition=True, still creates 1 resource.
    """
    if not condition:
        return 0
    
    return max(1, count)


def expand_dynamic_blocks(
    blocks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Expand dynamic blocks in configuration.

    BUG K12: Blocks are expanded in reverse order.
    """
    expanded = []

    for block in reversed(blocks):
        if block.get("for_each"):
            for item in block["for_each"]:
                expanded.append({**block, "value": item})
        else:
            expanded.append(block)
    return expanded


def validate_config_schema(
    config: Dict[str, Any],
    schema: Dict[str, Any],
    path: str = "",
) -> List[str]:
    """Validate a configuration dict against a schema definition.

    Returns a list of validation error strings. Empty list means valid.
    Schema entries: ``{"key": {"type": "str|int|float|dict|list", "required": bool, "children": {...}}}``
    """
    errors = []
    type_map = {"str": str, "int": int, "float": (int, float), "dict": dict, "list": list}

    for field_name, spec in schema.items():
        field_path = f"{path}.{field_name}" if path else field_name
        required = spec.get("required", False)
        expected_type = spec.get("type", "str")

        if field_name not in config:
            if required:
                errors.append(f"Missing required field: {field_path}")
            continue

        value = config[field_name]
        expected = type_map.get(expected_type)
        if expected and not isinstance(value, expected):
            errors.append(
                f"Type mismatch at {field_path}: expected {expected_type}, "
                f"got {type(value).__name__}"
            )

        if expected_type == "dict" and "children" in spec and isinstance(value, dict):
            child_errors = validate_config_schema(value, spec["children"], path)
            errors.extend(child_errors)

    return errors


def resolve_variable_chain(
    variables: Dict[str, str],
    start_key: str,
    max_depth: int = 50,
) -> Optional[str]:
    """Resolve a chain of variable references.

    Variables can reference other variables: a -> b -> c -> "final_value"
    Returns the final resolved value or None if chain is broken or circular.
    """
    visited = set()
    current = start_key
    depth = 0

    while current in variables and depth < max_depth:
        if current in visited:
            return None  # Circular
        visited.add(current)
        current = variables[current]
        depth += 1

    if current in variables:
        return None  # Hit depth limit

    return current
