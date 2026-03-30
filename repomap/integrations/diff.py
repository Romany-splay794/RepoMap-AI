"""repomap diff — show changed symbols and their blast radius."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from repomap.core.symbol_store import SymbolStore
from repomap.graph.builder import GraphBuilder
from repomap.graph.models import EdgeType, GraphEdge, GraphNode


@dataclass
class DiffSymbol:
    """A symbol that was directly changed."""
    name: str
    qualified_name: str
    kind: str
    file_path: str
    line_start: int


@dataclass
class BlastRadius:
    """The blast radius of a set of changes."""
    changed_symbols: list[DiffSymbol]
    affected_symbols: list[DiffSymbol]  # transitive callers/dependents
    changed_files: list[str]
    depth: int


def compute_diff(
    repo_root: Path,
    store: SymbolStore,
    ref: str = "HEAD~1",
    depth: int = 2,
) -> BlastRadius:
    """Compute changed symbols and their blast radius.

    1. Run `git diff <ref>` to get changed files and line ranges
    2. Map changed lines to affected symbols
    3. BFS upstream to find transitive dependents
    """
    changed_files, changed_ranges = _git_diff(repo_root, ref)

    if not changed_files:
        return BlastRadius(
            changed_symbols=[], affected_symbols=[],
            changed_files=[], depth=depth,
        )

    # Find symbols in changed line ranges
    changed_syms: list[DiffSymbol] = []
    changed_qnames: set[str] = set()

    for file_path, ranges in changed_ranges.items():
        rows = store.get_symbols_for_file(Path(file_path))
        for row in rows:
            if row["kind"] == "import":
                continue
            line_start = row["line_start"] or 0
            line_end = row["line_end"] or 0
            for rng_start, rng_end in ranges:
                if line_start <= rng_end and line_end >= rng_start:
                    ds = DiffSymbol(
                        name=row["name"],
                        qualified_name=row["qualified_name"],
                        kind=row["kind"],
                        file_path=row["file_path"],
                        line_start=line_start,
                    )
                    if ds.qualified_name not in changed_qnames:
                        changed_syms.append(ds)
                        changed_qnames.add(ds.qualified_name)
                    break

    # BFS upstream to find blast radius
    builder = GraphBuilder(store)
    all_nodes, all_edges = builder.build_from_store()

    # Build reverse adjacency (who calls/depends on the changed symbols)
    qname_to_node: dict[str, GraphNode] = {n.qualified_name: n for n in all_nodes}
    reverse_adj: dict[str, set[str]] = defaultdict(set)
    for edge in all_edges:
        if edge.target_id is not None:
            reverse_adj[edge.target_qualified_name].add(edge.source_qualified_name)

    # BFS from changed symbols
    visited: set[str] = set(changed_qnames)
    frontier = list(changed_qnames)
    for _ in range(depth):
        next_frontier: list[str] = []
        for qn in frontier:
            for caller in reverse_adj.get(qn, set()):
                if caller not in visited:
                    visited.add(caller)
                    next_frontier.append(caller)
        frontier = next_frontier

    affected_qnames = visited - changed_qnames
    affected_syms: list[DiffSymbol] = []
    for qn in sorted(affected_qnames):
        node = qname_to_node.get(qn)
        if node:
            affected_syms.append(DiffSymbol(
                name=node.name,
                qualified_name=node.qualified_name,
                kind=node.kind,
                file_path=node.file_path,
                line_start=node.line_start,
            ))

    return BlastRadius(
        changed_symbols=changed_syms,
        affected_symbols=affected_syms,
        changed_files=changed_files,
        depth=depth,
    )


def format_blast_radius(br: BlastRadius) -> str:
    """Format a blast radius result as human-readable text."""
    lines: list[str] = []

    lines.append(f"Changed files: {len(br.changed_files)}")
    for f in br.changed_files:
        lines.append(f"  {f}")
    lines.append("")

    lines.append(f"Changed symbols: {len(br.changed_symbols)}")
    for sym in br.changed_symbols:
        lines.append(f"  {sym.kind:10} {sym.qualified_name}  ({sym.file_path}:{sym.line_start})")
    lines.append("")

    lines.append(f"Blast radius ({br.depth}-hop): {len(br.affected_symbols)} affected symbols")
    for sym in br.affected_symbols:
        lines.append(f"  {sym.kind:10} {sym.qualified_name}  ({sym.file_path}:{sym.line_start})")

    return "\n".join(lines)


def _git_diff(
    repo_root: Path,
    ref: str,
) -> tuple[list[str], dict[str, list[tuple[int, int]]]]:
    """Run git diff and return changed files + changed line ranges per file.

    Returns (changed_file_list, {file_path: [(start_line, end_line), ...]}).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--unified=0", "--no-color", ref],
            capture_output=True, text=True, cwd=repo_root,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return [], {}

    if result.returncode != 0:
        return [], {}

    changed_files: list[str] = []
    ranges: dict[str, list[tuple[int, int]]] = defaultdict(list)
    current_file: str | None = None

    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            if current_file not in changed_files:
                changed_files.append(current_file)
        elif line.startswith("@@ ") and current_file:
            # Parse hunk header: @@ -old,count +new,count @@
            parts = line.split()
            if len(parts) >= 3:
                new_range = parts[2]  # +start,count or +start
                if "," in new_range:
                    start = int(new_range.split(",")[0].lstrip("+"))
                    count = int(new_range.split(",")[1])
                else:
                    start = int(new_range.lstrip("+"))
                    count = 1
                if count > 0:
                    ranges[current_file].append((start, start + count - 1))

    return changed_files, dict(ranges)
