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


def parallel_execution_groups(
    nodes: Sequence[str], edges: Iterable[Tuple[str, str]]
) -> List[Set[str]]:
    ordered = topological_sort(nodes, edges)
    edge_list = list(edges)
    children: Dict[str, List[str]] = defaultdict(list)
    has_parent: Set[str] = set()
    for src, tgt in edge_list:
        children[src].append(tgt)
        has_parent.add(tgt)

    level: Dict[str, int] = {}
    queue = deque()
    for node in ordered:
        if node not in has_parent:
            level[node] = 0
            queue.append(node)

    while queue:
        current = queue.popleft()
        for child in children[current]:
            if child not in level:
                level[child] = level[current] + 1
                queue.append(child)

    for node in ordered:
        if node not in level:
            level[node] = 0

    groups: Dict[int, Set[str]] = defaultdict(set)
    for node, lvl in level.items():
        groups[lvl].add(node)
    return [groups[i] for i in range(max(groups.keys()) + 1)] if groups else []
