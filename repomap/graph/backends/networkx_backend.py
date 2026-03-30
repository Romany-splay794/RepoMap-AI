"""NetworkX graph backend for Tier 1 (small repos < 1K files)."""

from __future__ import annotations

from repomap.graph.models import GraphEdge, GraphNode


def build_nx_graph(nodes: list[GraphNode], edges: list[GraphEdge]):
    """Build a NetworkX DiGraph from node and edge lists."""
    import networkx as nx

    G: nx.DiGraph = nx.DiGraph()
    for node in nodes:
        G.add_node(
            node.qualified_name,
            symbol_id=node.symbol_id,
            kind=node.kind,
            name=node.name,
            file_path=node.file_path,
            line_start=node.line_start,
            signature=node.signature,
            is_entry_point=node.is_entry_point,
            language=node.language,
        )
    for edge in edges:
        if not edge.source_qualified_name or not edge.target_qualified_name:
            continue
        # Ensure both endpoints exist as nodes (target may be external)
        if edge.target_qualified_name not in G:
            G.add_node(edge.target_qualified_name, kind="external", symbol_id=-1)
        G.add_edge(
            edge.source_qualified_name,
            edge.target_qualified_name,
            edge_type=str(edge.edge_type),
            confidence=edge.confidence,
            edge_id=edge.id,
        )
    return G
