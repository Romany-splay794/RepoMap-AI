"""Graph builder: converts SQLite symbols+edges into GraphNode/GraphEdge lists."""

from __future__ import annotations

import json
from collections import deque

from repomap.core.symbol_store import SymbolStore
from repomap.graph.models import EdgeType, GraphEdge, GraphNode


class GraphBuilder:
    def __init__(self, store: SymbolStore) -> None:
        self._store = store

    def build_from_store(self) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Load all symbols and edges from SQLite into in-memory graph objects."""
        nodes = self._load_nodes()
        edges = self._load_edges(nodes)
        return nodes, edges

    def build_subgraph(
        self,
        seed_qualified_names: list[str],
        depth: int = 2,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """BFS from seed nodes up to `depth` hops. Includes both callers and callees."""
        all_nodes, all_edges = self.build_from_store()
        node_map = {n.qualified_name: n for n in all_nodes}

        # Build adjacency (bidirectional for subgraph extraction)
        adjacency: dict[str, set[str]] = {n.qualified_name: set() for n in all_nodes}
        for edge in all_edges:
            if edge.source_qualified_name in adjacency:
                adjacency[edge.source_qualified_name].add(edge.target_qualified_name)
            if edge.target_qualified_name in adjacency:
                adjacency[edge.target_qualified_name].add(edge.source_qualified_name)

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        for seed in seed_qualified_names:
            if seed in node_map:
                queue.append((seed, 0))
                visited.add(seed)

        while queue:
            qname, d = queue.popleft()
            if d >= depth:
                continue
            for neighbor in adjacency.get(qname, set()):
                if neighbor not in visited and neighbor in node_map:
                    visited.add(neighbor)
                    queue.append((neighbor, d + 1))

        sub_nodes = [node_map[qn] for qn in visited if qn in node_map]
        sub_ids = {n.symbol_id for n in sub_nodes}
        sub_edges = [
            e for e in all_edges
            if e.source_id in sub_ids and (e.target_id is None or e.target_id in sub_ids)
        ]
        return sub_nodes, sub_edges

    def _load_nodes(self) -> list[GraphNode]:
        nodes: list[GraphNode] = []
        dm_map: dict[int, tuple[str, list]] = {}
        for dm_row in self._store.get_all_data_models():
            fields = json.loads(dm_row["fields_json"] or "[]")
            dm_map[dm_row["symbol_id"]] = (dm_row["framework"], fields)

        for row in self._store.get_all_symbols():
            dm_framework, dm_fields = dm_map.get(row["id"], (None, []))
            node = GraphNode(
                symbol_id=row["id"],
                qualified_name=row["qualified_name"],
                name=row["name"],
                kind=row["kind"],
                file_path=row["file_path"],
                line_start=row["line_start"] or 0,
                line_end=row["line_end"] or 0,
                signature=row["signature"] or "",
                language=row["language"] or "",
                is_entry_point=bool(row["is_entry_point"]),
                is_exported=bool(row["is_exported"]),
                data_model_framework=dm_framework,
                data_model_fields=dm_fields,
            )
            nodes.append(node)
        return nodes

    def _load_edges(self, nodes: list[GraphNode]) -> list[GraphEdge]:
        id_to_qname: dict[int, str] = {n.symbol_id: n.qualified_name for n in nodes}
        edges: list[GraphEdge] = []
        for row in self._store.get_all_edges():
            try:
                etype = EdgeType(row["edge_type"])
            except ValueError:
                etype = EdgeType.CALLS

            source_qname = id_to_qname.get(row["source_id"], "")
            target_id = row["target_id"]
            target_qname = (
                id_to_qname.get(target_id, row["target_qualified_name"])
                if target_id is not None
                else row["target_qualified_name"]
            )

            edge = GraphEdge(
                id=row["id"],
                source_id=row["source_id"],
                target_id=target_id,
                source_qualified_name=source_qname,
                target_qualified_name=target_qname,
                edge_type=etype,
                confidence=row["confidence"] or 1.0,
            )
            edges.append(edge)
        return edges
