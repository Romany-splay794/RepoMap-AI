"""Heuristic-based module narrative summaries — no LLM required."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from repomap.graph.models import EdgeType, GraphEdge, GraphNode


# ── Pattern matchers for purpose inference ────────────────────────────────────

_CRUD_VERBS = {"create", "read", "update", "delete", "insert", "upsert", "remove",
               "save", "fetch", "load", "store", "get", "set", "put", "patch", "list"}

_HTTP_PATTERNS = {"route", "router", "handler", "controller", "endpoint", "view",
                  "api", "resource", "rest"}

_DB_PATTERNS = {"query", "repository", "repo", "dao", "store", "database", "db",
                "migration", "schema", "model", "orm"}

_AUTH_PATTERNS = {"auth", "login", "logout", "session", "token", "jwt", "oauth",
                  "permission", "role", "acl", "credential", "password"}

_TEST_PATTERNS = {"test", "spec", "fixture", "mock", "stub", "fake", "assert"}

_CONFIG_PATTERNS = {"config", "settings", "env", "constants", "defaults", "options"}

_CLI_PATTERNS = {"cli", "command", "arg", "flag", "option", "parse", "typer", "click"}

_UTIL_PATTERNS = {"util", "utils", "helper", "helpers", "common", "shared", "lib", "tools"}

# Import-based framework hints
_IMPORT_HINTS: dict[str, str] = {
    "flask": "HTTP API layer (Flask)",
    "fastapi": "HTTP API layer (FastAPI)",
    "django": "Django web framework",
    "express": "HTTP API layer (Express)",
    "sqlalchemy": "database/ORM layer (SQLAlchemy)",
    "prisma": "database layer (Prisma)",
    "pytest": "test suite",
    "unittest": "test suite",
    "jest": "test suite",
    "react": "React UI component",
    "vue": "Vue UI component",
    "typer": "CLI interface",
    "click": "CLI interface",
    "celery": "async task queue",
    "redis": "cache/queue layer (Redis)",
    "kafka": "event streaming layer",
    "grpc": "gRPC service layer",
    "graphql": "GraphQL API layer",
    "pydantic": "data validation layer",
    "logging": "logging/observability",
    "sentry": "error tracking",
}


def generate_narratives(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
) -> dict[str, str]:
    """Return {module_path: one-sentence summary} for each module.

    A "module" is the top-level directory or the file itself for root-level files.
    """
    # Group nodes by module path
    module_nodes: dict[str, list[GraphNode]] = defaultdict(list)
    for node in nodes:
        module = _module_key(node.file_path)
        module_nodes[module].append(node)

    # Group edges by module (source side)
    node_id_to_module: dict[int, str] = {}
    for node in nodes:
        node_id_to_module[node.symbol_id] = _module_key(node.file_path)

    module_edges: dict[str, list[GraphEdge]] = defaultdict(list)
    for edge in edges:
        mod = node_id_to_module.get(edge.source_id)
        if mod:
            module_edges[mod].append(edge)

    summaries: dict[str, str] = {}
    for module, mnodes in sorted(module_nodes.items()):
        summary = _infer_purpose(module, mnodes, module_edges.get(module, []))
        if summary:
            summaries[module] = summary

    return summaries


def _module_key(file_path: str) -> str:
    """Extract a module key from a file path."""
    parts = Path(file_path).parts
    if len(parts) >= 2:
        return parts[0]
    return Path(file_path).stem


def _infer_purpose(
    module: str,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
) -> str:
    """Infer the purpose of a module from its symbols and edges."""
    module_lower = module.lower()
    func_names = [n.name.lower() for n in nodes if n.kind in ("function", "method")]
    all_names = [n.name.lower() for n in nodes]
    signatures = [n.signature.lower() for n in nodes if n.signature]

    # 1. Check module name patterns
    for pattern_set, label in [
        (_HTTP_PATTERNS, "HTTP API / request handling"),
        (_DB_PATTERNS, "data access / persistence"),
        (_AUTH_PATTERNS, "authentication / authorization"),
        (_TEST_PATTERNS, "test suite"),
        (_CONFIG_PATTERNS, "configuration"),
        (_CLI_PATTERNS, "CLI interface"),
        (_UTIL_PATTERNS, "shared utilities"),
    ]:
        if any(p in module_lower for p in pattern_set):
            entry_count = sum(1 for n in nodes if n.is_entry_point)
            class_count = sum(1 for n in nodes if n.kind == "class")
            return _format_summary(label, len(nodes), entry_count, class_count)

    # 2. Analyze function name patterns
    verb_counts = Counter()
    for name in func_names:
        # Split camelCase / snake_case
        words = set(re.split(r"[_A-Z]", name.lower()))
        for word in words:
            if word in _CRUD_VERBS:
                verb_counts[word] += 1

    if verb_counts:
        top_verbs = verb_counts.most_common(3)
        total_crud = sum(c for _, c in top_verbs)
        if total_crud > len(func_names) * 0.3:
            return _format_summary("data access layer (CRUD operations)", len(nodes),
                                   sum(1 for n in nodes if n.is_entry_point),
                                   sum(1 for n in nodes if n.kind == "class"))

    # 3. Check edge types
    if edges:
        read_count = sum(1 for e in edges if e.edge_type == EdgeType.READS)
        write_count = sum(1 for e in edges if e.edge_type == EdgeType.WRITES)
        call_count = sum(1 for e in edges if e.edge_type == EdgeType.CALLS)
        if (read_count + write_count) > call_count * 0.5 and (read_count + write_count) > 2:
            return _format_summary("data processing (heavy read/write)", len(nodes),
                                   sum(1 for n in nodes if n.is_entry_point),
                                   sum(1 for n in nodes if n.kind == "class"))

    # 4. Check entry points
    entry_count = sum(1 for n in nodes if n.is_entry_point)
    if entry_count > len(nodes) * 0.3 and entry_count >= 2:
        return _format_summary("API endpoint handlers", len(nodes), entry_count,
                               sum(1 for n in nodes if n.kind == "class"))

    # 5. Check data models
    model_count = sum(1 for n in nodes if n.data_model_framework)
    if model_count > len(nodes) * 0.3:
        return _format_summary("data model definitions", len(nodes), entry_count, model_count)

    # 6. Fallback: describe by composition
    class_count = sum(1 for n in nodes if n.kind == "class")
    func_count = sum(1 for n in nodes if n.kind == "function")
    method_count = sum(1 for n in nodes if n.kind == "method")

    if class_count > func_count:
        return f"Object-oriented module with {class_count} classes and {method_count} methods."
    if func_count > 0:
        return f"Module with {func_count} functions and {class_count} classes."
    return ""


def _format_summary(label: str, total: int, entries: int, classes: int) -> str:
    parts = [label.capitalize()]
    details = []
    if entries:
        details.append(f"{entries} entry points")
    if classes:
        details.append(f"{classes} classes")
    details.append(f"{total} symbols total")
    parts.append(f" ({', '.join(details)}).")
    return "".join(parts)
