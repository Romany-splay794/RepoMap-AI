"""Cross-file reference resolver: turns target_qualified_name → target_id."""

from __future__ import annotations

import json
from pathlib import Path

from repomap.core.symbol_store import SymbolStore


class ReferenceResolver:
    def __init__(self, store: SymbolStore, repo_root: Path) -> None:
        self._store = store
        self._repo_root = repo_root
        # Build in-memory lookup caches
        self._by_qname: dict[str, int] = {}
        self._by_name: dict[str, list[tuple[int, str]]] = {}  # name → [(id, file_path)]
        self._refresh_caches()

    def _refresh_caches(self) -> None:
        self._by_qname.clear()
        self._by_name.clear()
        for row in self._store.get_all_symbols():
            self._by_qname[row["qualified_name"]] = row["id"]
            name = row["name"]
            if name not in self._by_name:
                self._by_name[name] = []
            self._by_name[name].append((row["id"], row["file_path"]))

    def resolve_all(self) -> tuple[int, int]:
        """Resolve all pending edges. Returns (resolved_count, unresolved_count)."""
        self._refresh_caches()
        edges = self._store.get_unresolved_edges()
        resolved = 0
        unresolved = 0
        for edge in edges:
            target_name = edge["target_qualified_name"]
            source_id = edge["source_id"]
            result = self._resolve(target_name, source_id)
            if result is not None:
                target_id, confidence = result
                self._store.resolve_edge(edge["id"], target_id, confidence)
                resolved += 1
            else:
                self._store.update_edge_confidence(edge["id"], 0.5)
                unresolved += 1
        return resolved, unresolved

    def _resolve(
        self, target_name: str, source_id: int
    ) -> tuple[int, float] | None:
        # Skip obvious externals / builtins
        if target_name in _PYTHON_BUILTINS or target_name in _COMMON_EXTERNALS:
            return None

        # 1. Exact qualified name match
        if target_name in self._by_qname:
            return self._by_qname[target_name], 1.0

        # 2. Suffix: just the short name
        short_name = target_name.split(".")[-1]
        if short_name in self._by_name:
            candidates = self._by_name[short_name]
            if len(candidates) == 1:
                return candidates[0][0], 0.9
            # Prefer same-file candidate
            source_row = self._store.get_symbol_by_id(source_id)
            if source_row:
                same_file = [
                    (sid, fp) for sid, fp in candidates
                    if fp == source_row["file_path"]
                ]
                if same_file:
                    return same_file[0][0], 0.9
            # Pick first (best effort)
            return candidates[0][0], 0.7

        # 3. Module-prefixed: check if any symbol's qname ends with target_name
        for qname, sid in self._by_qname.items():
            if qname.endswith(f".{target_name}") or qname.endswith(f".{short_name}"):
                return sid, 0.8

        return None


_PYTHON_BUILTINS = frozenset({
    "print", "len", "range", "enumerate", "zip", "map", "filter",
    "list", "dict", "set", "tuple", "str", "int", "float", "bool",
    "type", "isinstance", "issubclass", "hasattr", "getattr", "setattr",
    "super", "object", "Exception", "ValueError", "TypeError", "KeyError",
    "AttributeError", "RuntimeError", "StopIteration", "NotImplementedError",
    "open", "next", "iter", "sorted", "reversed", "any", "all", "min", "max",
    "sum", "abs", "round", "repr", "format", "vars", "dir", "id",
    "staticmethod", "classmethod", "property", "append", "extend", "update",
    "commit", "rollback", "add", "flush", "close", "get", "post",
})

_COMMON_EXTERNALS = frozenset({
    "os", "sys", "re", "json", "datetime", "pathlib", "typing", "abc",
    "dataclasses", "functools", "itertools", "collections", "logging",
    "asyncio", "threading", "subprocess", "shutil", "copy", "math",
    "random", "time", "uuid", "hashlib", "base64", "io", "contextlib",
    "pydantic", "fastapi", "flask", "django", "sqlalchemy", "aiohttp",
    "requests", "httpx", "pytest", "unittest", "click", "typer",
    "numpy", "pandas", "torch", "tensorflow",
})
