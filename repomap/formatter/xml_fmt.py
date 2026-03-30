"""XML formatter for Claude-optimized <repo_context> output."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from repomap.graph.models import EdgeType, GraphEdge, GraphNode


def _esc(s: str) -> str:
    """XML-escape a string for use in attribute values."""
    return (
        s.replace("&", "&amp;")
         .replace('"', "&quot;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


class XMLFormatter:
    def render(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        total: int,
    ) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        file_count = len({n.file_path for n in nodes})

        # Build edge lookups
        calls_map: dict[int, list[str]] = defaultdict(list)
        reads_map: dict[int, list[str]] = defaultdict(list)
        writes_map: dict[int, list[str]] = defaultdict(list)
        extends_map: dict[int, list[str]] = defaultdict(list)
        implements_map: dict[int, list[str]] = defaultdict(list)
        for edge in edges:
            tname = edge.target_qualified_name.split(".")[-1]
            if edge.edge_type == EdgeType.CALLS:
                calls_map[edge.source_id].append(tname)
            elif edge.edge_type == EdgeType.READS:
                reads_map[edge.source_id].append(tname)
            elif edge.edge_type == EdgeType.WRITES:
                writes_map[edge.source_id].append(tname)
            elif edge.edge_type == EdgeType.EXTENDS:
                extends_map[edge.source_id].append(tname)
            elif edge.edge_type == EdgeType.IMPLEMENTS:
                implements_map[edge.source_id].append(tname)

        # Data model read/write by model_id
        dm_reads: dict[int, list[str]] = defaultdict(list)
        dm_writes: dict[int, list[str]] = defaultdict(list)
        id_to_name = {n.symbol_id: n.name for n in nodes}
        for edge in edges:
            if edge.target_id is None:
                continue
            src_name = id_to_name.get(edge.source_id, "")
            if edge.edge_type == EdgeType.READS:
                dm_reads[edge.target_id].append(src_name)
            elif edge.edge_type == EdgeType.WRITES:
                dm_writes[edge.target_id].append(src_name)

        lines: list[str] = []
        lines.append(
            f'<repo_context generated="{ts}" files="{file_count}" '
            f'symbols="{len(nodes)}" total="{total}">'
        )

        # ── Module narratives ─────────────────────────────────────────────────
        seen_narratives: dict[str, str] = {}
        for n in nodes:
            if n.narrative:
                mod = Path(n.file_path).parts[0] if n.file_path else ""
                if mod not in seen_narratives:
                    seen_narratives[mod] = n.narrative
        if seen_narratives:
            lines.append("  <module_summaries>")
            for mod, narr in sorted(seen_narratives.items()):
                lines.append(f'    <summary module="{_esc(mod)}">{_esc(narr)}</summary>')
            lines.append("  </module_summaries>")

        # ── Entry points ──────────────────────────────────────────────────────
        entry_nodes = [n for n in nodes if n.is_entry_point]
        if entry_nodes:
            lines.append("  <entry_points>")
            for n in entry_nodes:
                sig_attr = f' sig="{_esc(n.signature)}"' if n.signature else ""
                lines.append(
                    f'    <entry name="{_esc(n.name)}" '
                    f'file="{_esc(n.file_path)}:{n.line_start}"{sig_attr}/>'
                )
            lines.append("  </entry_points>")

        # ── Data models ───────────────────────────────────────────────────────
        model_nodes = [n for n in nodes if n.data_model_framework]
        if model_nodes:
            lines.append("  <data_models>")
            for mn in model_nodes:
                fields_str = ""
                if mn.data_model_fields:
                    parts = []
                    for f in mn.data_model_fields:
                        opt = "?" if f.get("optional") else ""
                        parts.append(f"{f['name']}:{f['type']}{opt}")
                    fields_str = f' fields="{_esc(",".join(parts))}"'
                readers = dm_reads.get(mn.symbol_id, [])
                writers = dm_writes.get(mn.symbol_id, [])
                read_attr = f' read_by="{_esc(",".join(readers))}"' if readers else ""
                write_attr = f' written_by="{_esc(",".join(writers))}"' if writers else ""
                lines.append(
                    f'    <model name="{_esc(mn.name)}" '
                    f'framework="{_esc(mn.data_model_framework or "")}" '
                    f'file="{_esc(mn.file_path)}:{mn.line_start}"'
                    f'{fields_str}{read_attr}{write_attr}/>'
                )
            lines.append("  </data_models>")

        # ── Symbols grouped by module (top-level dir) ─────────────────────────
        by_module: dict[str, list[GraphNode]] = defaultdict(list)
        for n in nodes:
            if n.data_model_framework:
                continue
            module = Path(n.file_path).parts[0] if n.file_path else "root"
            by_module[module].append(n)

        for module, mnodes in sorted(by_module.items()):
            lines.append(f'  <module path="{_esc(module)}">')
            # Group by class within module
            by_class: dict[str | None, list[GraphNode]] = defaultdict(list)
            for n in mnodes:
                # Guess class membership from qualified_name
                parts = n.qualified_name.split(".")
                cls = parts[-2] if len(parts) >= 3 else None
                by_class[cls].append(n)

            for cls_name, cls_nodes in sorted(by_class.items(), key=lambda x: x[0] or ""):
                if cls_name:
                    lines.append(f'    <class name="{_esc(cls_name)}">')
                    indent = "      "
                else:
                    indent = "    "
                for n in sorted(cls_nodes, key=lambda x: x.line_start):
                    attrs = _node_attrs(n, calls_map, reads_map, writes_map,
                                       extends_map, implements_map)
                    tag = "method" if n.kind == "method" else "function"
                    if n.kind == "class":
                        tag = "class_def"
                    lines.append(f"{indent}<{tag}{attrs}/>")
                if cls_name:
                    lines.append("    </class>")
            lines.append("  </module>")

        # ── Footer ────────────────────────────────────────────────────────────
        if total > len(nodes):
            lines.append(
                f'  <footer showing="{len(nodes)}" total="{total}" '
                f'hint="Use --around &lt;target&gt; for a focused view"/>'
            )
        lines.append("</repo_context>")
        return "\n".join(lines)

    def render_prepend(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        total: int,
        repo_name: str = "",
    ) -> str:
        """Render XML wrapped in a system-prompt-ready <repository_context> tag."""
        inner = self.render(nodes, edges, total)
        return (
            "<repository_context>\n"
            f"  <!-- RepoMap: token-efficient structural context for {repo_name} -->\n"
            f"{inner}\n"
            "</repository_context>"
        )


def _node_attrs(
    n: GraphNode,
    calls_map, reads_map, writes_map, extends_map, implements_map,
) -> str:
    parts = [f' name="{_esc(n.name)}"']
    if n.signature:
        parts.append(f' sig="{_esc(n.signature)}"')
    parts.append(f' file="{_esc(n.file_path)}:{n.line_start}"')
    if calls := calls_map.get(n.symbol_id):
        parts.append(f' calls="{_esc(",".join(calls[:10]))}"')
    if reads := reads_map.get(n.symbol_id):
        parts.append(f' reads="{_esc(",".join(reads))}"')
    if writes := writes_map.get(n.symbol_id):
        parts.append(f' writes="{_esc(",".join(writes))}"')
    if extends := extends_map.get(n.symbol_id):
        parts.append(f' extends="{_esc(",".join(extends))}"')
    if implements := implements_map.get(n.symbol_id):
        parts.append(f' implements="{_esc(",".join(implements))}"')
    if n.is_hot_path:
        parts.append(' hot_path="true"')
    return "".join(parts)
