"""Markdown formatter for .repomap.md output."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from repomap.graph.models import EdgeType, GraphEdge, GraphNode


class MarkdownFormatter:
    def render(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        total: int,
    ) -> str:
        showing = len(nodes)
        lines: list[str] = []

        # ── Header ────────────────────────────────────────────────────────────
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        file_count = len({n.file_path for n in nodes})
        lines.append(f"# RepoMap")
        lines.append(
            f"> Generated {ts} | {file_count} files | {showing} symbols"
            + (f" (of {total})" if total > showing else "")
        )
        lines.append("")

        # ── Entry Points ──────────────────────────────────────────────────────
        entry_nodes = [n for n in nodes if n.is_entry_point]
        if entry_nodes:
            lines.append("## Entry Points")
            for n in entry_nodes:
                loc = f"{n.file_path}:{n.line_start}"
                lines.append(f"- `{n.name}` — `{loc}`")
            lines.append("")

        # ── Data Models ───────────────────────────────────────────────────────
        model_nodes = [n for n in nodes if n.data_model_framework]
        if model_nodes:
            lines.append("## Data Models")
            # Build read/write lookup
            reads_map: dict[int, list[str]] = defaultdict(list)
            writes_map: dict[int, list[str]] = defaultdict(list)
            node_id_to_name: dict[int, str] = {n.symbol_id: n.name for n in nodes}
            for edge in edges:
                if edge.target_id is None:
                    continue
                if edge.edge_type == EdgeType.READS:
                    reads_map[edge.target_id].append(
                        node_id_to_name.get(edge.source_id, "?")
                    )
                elif edge.edge_type == EdgeType.WRITES:
                    writes_map[edge.target_id].append(
                        node_id_to_name.get(edge.source_id, "?")
                    )
            for mn in model_nodes:
                lines.append(f"### {mn.name} (`{mn.file_path}:{mn.line_start}`)")
                lines.append(f"*{mn.data_model_framework}*")
                if mn.data_model_fields:
                    lines.append("| Field | Type | Optional |")
                    lines.append("|-------|------|----------|")
                    for f in mn.data_model_fields:
                        opt = "yes" if f.get("optional") else "no"
                        lines.append(f"| {f['name']} | {f['type']} | {opt} |")
                readers = reads_map.get(mn.symbol_id)
                writers = writes_map.get(mn.symbol_id)
                if readers:
                    lines.append(f"\n**Read by:** {', '.join(f'`{r}`' for r in readers)}")
                if writers:
                    lines.append(f"**Written by:** {', '.join(f'`{w}`' for w in writers)}")
                lines.append("")

        # ── Hot Paths ─────────────────────────────────────────────────────────
        hot_nodes = [n for n in nodes if n.is_hot_path and not n.is_entry_point]
        if hot_nodes:
            lines.append("## Hot Path Functions")
            lines.append("> Functions on critical execution paths from entry points.")
            for n in hot_nodes[:20]:
                loc = f"{n.file_path}:{n.line_start}"
                lines.append(f"- `{n.name}` — `{loc}`")
            lines.append("")

        # ── Module Narratives ─────────────────────────────────────────────────
        narr_modules = {n.narrative for n in nodes if n.narrative}
        if narr_modules:
            seen_narratives: dict[str, str] = {}
            for n in nodes:
                if n.narrative:
                    mod = Path(n.file_path).parts[0] if n.file_path else ""
                    if mod not in seen_narratives:
                        seen_narratives[mod] = n.narrative
            if seen_narratives:
                lines.append("## Module Summaries")
                for mod, narr in sorted(seen_narratives.items()):
                    lines.append(f"- **{mod}**: {narr}")
                lines.append("")

        # ── Symbols by file ───────────────────────────────────────────────────
        lines.append("## Symbols")
        by_file: dict[str, list[GraphNode]] = defaultdict(list)
        for n in nodes:
            if n.data_model_framework:
                continue  # already shown in Data Models section
            by_file[n.file_path].append(n)

        # Build edge lookup: source_id → list of edges
        edge_by_source: dict[int, list[GraphEdge]] = defaultdict(list)
        for edge in edges:
            edge_by_source[edge.source_id].append(edge)

        for file_path in sorted(by_file.keys()):
            file_nodes = by_file[file_path]
            lines.append(f"\n### `{file_path}`")
            for n in sorted(file_nodes, key=lambda x: x.line_start):
                if n.signature:
                    lines.append(f"```\n{n.signature}\n```")
                else:
                    lines.append(f"- `{n.name}` ({n.kind})")
                # Render outgoing edges
                node_edges = edge_by_source.get(n.symbol_id, [])
                _render_edges(lines, node_edges, n.symbol_id)

        # ── Footer ────────────────────────────────────────────────────────────
        if total > showing:
            lines.append(
                f"\n---\n"
                f"Showing {showing} of {total} symbols (ranked by importance). "
                f"Use `--around <target>` for a focused view."
            )

        return "\n".join(lines)


def _render_edges(
    lines: list[str],
    node_edges: list[GraphEdge],
    source_id: int,
) -> None:
    grouped: dict[EdgeType, list[tuple[str, str]]] = defaultdict(list)
    for edge in node_edges:
        grouped[edge.edge_type].append((edge.target_qualified_name, edge.display_arrow))

    type_order = [EdgeType.CALLS, EdgeType.READS, EdgeType.WRITES,
                  EdgeType.IMPORTS, EdgeType.EXTENDS, EdgeType.IMPLEMENTS]
    for etype in type_order:
        entries = grouped.get(etype)
        if not entries:
            continue
        # Separate confident vs uncertain
        confident = [name for name, arrow in entries if arrow == "→"]
        uncertain = [name for name, arrow in entries if arrow == "?→"]
        # Use just the last component for readability
        def short(qn: str) -> str:
            return qn.split(".")[-1] if "." in qn else qn
        if confident:
            names_str = ", ".join(f"`{short(n)}`" for n in confident[:8])
            lines.append(f"→ {etype}: {names_str}")
        if uncertain:
            names_str = ", ".join(f"`{short(n)}`" for n in uncertain[:5])
            lines.append(f"?→ {etype}: {names_str}")
