"""Hot path detection — identifies functions on critical execution paths."""

from __future__ import annotations

from collections import defaultdict

from repomap.graph.models import EdgeType, GraphEdge, GraphNode


def detect_hot_paths(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    top_percentile: float = 0.20,
) -> set[int]:
    """Identify 'hot path' symbol IDs — functions frequently traversed from entry points.

    Algorithm:
    1. Find all entry-point nodes
    2. DFS from each entry point following CALLS edges
    3. Count how many entry-point paths pass through each function
    4. Top `top_percentile` by path frequency = hot path functions

    Returns a set of symbol_id values.
    """
    entry_nodes = [n for n in nodes if n.is_entry_point]
    if not entry_nodes:
        return set()

    # Build call adjacency: source_id → [target_id, ...]
    call_adj: dict[int, list[int]] = defaultdict(list)
    for edge in edges:
        if edge.edge_type == EdgeType.CALLS and edge.target_id is not None:
            call_adj[edge.source_id].append(edge.target_id)

    node_ids = {n.symbol_id for n in nodes}
    # Count how many entry-point DFS trees pass through each node
    path_counts: dict[int, int] = defaultdict(int)

    for entry in entry_nodes:
        visited: set[int] = set()
        _dfs(entry.symbol_id, call_adj, visited, node_ids)
        for sid in visited:
            path_counts[sid] += 1

    if not path_counts:
        return set()

    # Determine threshold
    counts = sorted(path_counts.values(), reverse=True)
    threshold_idx = max(1, int(len(counts) * top_percentile))
    threshold = counts[min(threshold_idx, len(counts) - 1)]

    return {sid for sid, count in path_counts.items() if count >= threshold}


def _dfs(
    node_id: int,
    adj: dict[int, list[int]],
    visited: set[int],
    valid_ids: set[int],
    max_depth: int = 20,
    _depth: int = 0,
) -> None:
    """Depth-first traversal from a node, bounded by max_depth."""
    if node_id in visited or _depth >= max_depth:
        return
    if node_id not in valid_ids:
        return
    visited.add(node_id)
    for neighbor in adj.get(node_id, []):
        _dfs(neighbor, adj, visited, valid_ids, max_depth, _depth + 1)


def annotate_hot_paths(
    nodes: list[GraphNode],
    hot_ids: set[int],
) -> None:
    """Set `is_hot_path` on nodes that are in the hot path set."""
    for node in nodes:
        node.is_hot_path = node.symbol_id in hot_ids
