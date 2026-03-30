"""Visual explorer generator — produces a self-contained .repomap.html file."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from repomap.graph.models import GraphEdge, GraphNode


_TEMPLATE_PATH = Path(__file__).parent / "template.html"

# Max nodes to render in the visual (performance threshold)
_MAX_NODES = 1500
# Max edges (too many edges make the canvas unreadable)
_MAX_EDGES = 8000


def _module_from_path(file_path: str, repo_root: str) -> str:
    """Extract top-level module name from a file path."""
    try:
        rel = Path(file_path).relative_to(Path(repo_root))
        return rel.parts[0] if rel.parts else "root"
    except ValueError:
        return Path(file_path).parts[-2] if len(Path(file_path).parts) >= 2 else "root"


def generate_html(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    repo_root: str,
    repo_name: str | None = None,
    max_nodes: int = _MAX_NODES,
) -> str:
    """Generate a self-contained HTML visual explorer.

    Returns the full HTML string.
    """
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    # Sort by pagerank descending, take top N
    sorted_nodes = sorted(nodes, key=lambda n: n.pagerank, reverse=True)
    if len(sorted_nodes) > max_nodes:
        sorted_nodes = sorted_nodes[:max_nodes]
    node_ids = {n.symbol_id for n in sorted_nodes}

    # Filter edges to only those where both endpoints are in the node set
    filtered_edges = [
        e for e in edges
        if e.source_id in node_ids and e.target_id is not None and e.target_id in node_ids
    ][:_MAX_EDGES]

    # Build JSON node objects
    json_nodes = []
    for n in sorted_nodes:
        json_nodes.append({
            "id": n.symbol_id,
            "name": n.name,
            "qualified_name": n.qualified_name,
            "kind": n.kind,
            "file": n.file_path,
            "line": n.line_start,
            "signature": n.signature[:160] if n.signature else "",
            "language": n.language,
            "module": _module_from_path(n.file_path, repo_root),
            "pagerank": round(n.pagerank, 8),
            "is_entry_point": n.is_entry_point,
            "data_model": n.data_model_framework,
        })

    # Build JSON edge objects
    json_edges = []
    for e in filtered_edges:
        json_edges.append({
            "source": e.source_id,
            "target": e.target_id,
            "type": str(e.edge_type),
            "confidence": round(e.confidence, 2),
        })

    # Stats string
    file_count = len({n.file_path for n in sorted_nodes})
    stats_str = (
        f"{file_count} files · {len(sorted_nodes)} symbols"
        + (f" of {len(nodes)}" if len(nodes) > len(sorted_nodes) else "")
        + f" · {len(json_edges)} edges"
    )

    graph_data = json.dumps(
        {"nodes": json_nodes, "edges": json_edges},
        separators=(",", ":"),  # compact JSON to reduce file size
    )

    name = repo_name or Path(repo_root).name

    # Inject into template
    html = template
    html = html.replace("{{repo_name}}", _esc_html(name))
    html = html.replace("{{stats}}", _esc_html(stats_str))
    html = html.replace("{{graph_data}}", graph_data)

    return html


def _esc_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
