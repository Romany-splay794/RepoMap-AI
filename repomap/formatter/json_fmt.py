"""JSON formatter for .repomap.json output."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from repomap.graph.models import EdgeType, GraphEdge, GraphNode


class JSONFormatter:
    def render(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        total: int,
    ) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        file_count = len({n.file_path for n in nodes})

        symbols = []
        for n in nodes:
            sym: dict = {
                "id": n.symbol_id,
                "name": n.name,
                "qualified_name": n.qualified_name,
                "kind": n.kind,
                "file": n.file_path,
                "line": n.line_start,
                "signature": n.signature,
                "language": n.language,
                "is_entry_point": n.is_entry_point,
                "pagerank": round(n.pagerank, 6),
            }
            if n.data_model_framework:
                sym["data_model"] = {
                    "framework": n.data_model_framework,
                    "fields": n.data_model_fields,
                }
            symbols.append(sym)

        edge_list = []
        for e in edges:
            edge_list.append({
                "source": e.source_qualified_name,
                "target": e.target_qualified_name,
                "type": str(e.edge_type),
                "confidence": e.confidence,
                "arrow": e.display_arrow,
            })

        entry_points = [
            {
                "name": n.name,
                "qualified_name": n.qualified_name,
                "file": n.file_path,
                "line": n.line_start,
                "signature": n.signature,
            }
            for n in nodes if n.is_entry_point
        ]

        data_models = [
            {
                "name": n.name,
                "qualified_name": n.qualified_name,
                "file": n.file_path,
                "framework": n.data_model_framework,
                "fields": n.data_model_fields,
            }
            for n in nodes if n.data_model_framework
        ]

        output = {
            "version": "1.0",
            "generated_at": ts,
            "stats": {
                "files": file_count,
                "symbols_showing": len(nodes),
                "symbols_total": total,
                "edges": len(edges),
            },
            "entry_points": entry_points,
            "data_models": data_models,
            "symbols": symbols,
            "edges": edge_list,
        }

        if total > len(nodes):
            output["truncated"] = True
            output["hint"] = (
                f"Showing {len(nodes)} of {total} symbols. "
                "Use --around <target> for a focused view."
            )

        return json.dumps(output, indent=2)
