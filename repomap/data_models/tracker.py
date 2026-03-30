"""Data model tracker: determines which functions read/write which models."""

from __future__ import annotations

import json
import re
from pathlib import Path

from repomap.core.symbol_store import SymbolStore


class DataModelTracker:
    """Analyzes function symbols and creates READS/WRITES edges to data models."""

    def __init__(self, store: SymbolStore) -> None:
        self._store = store

    def track(self) -> int:
        """Add reads/writes edges between functions and data models. Returns edge count."""
        # Build a name → symbol_id map of known data models
        model_rows = self._store.get_all_data_models()
        model_names: dict[str, int] = {
            row["name"]: row["symbol_id"] for row in model_rows
        }
        if not model_names:
            return 0

        count = 0
        for row in self._store.get_all_symbols():
            if row["kind"] not in ("function", "method"):
                continue
            sig = row["signature"] or ""
            # Check signature for type annotations referencing models
            for model_name, model_id in model_names.items():
                writes = self._is_writer(row, model_name, sig)
                reads = self._is_reader(row, model_name, sig)
                source_id = row["id"]
                if writes:
                    self._store.insert_edge(
                        source_id, model_id, model_name, "writes", 0.8
                    )
                    count += 1
                elif reads:
                    self._store.insert_edge(
                        source_id, model_id, model_name, "reads", 0.8
                    )
                    count += 1
        return count

    def _is_writer(self, row, model_name: str, sig: str) -> bool:
        """Heuristic: does this function write/create the model?"""
        name_lower = row["name"].lower()
        model_lower = model_name.lower()
        # Return type annotation contains model name
        if f"-> {model_name}" in sig or f"-> list[{model_name}" in sig.lower():
            return True
        # Function name suggests creation
        if any(x in name_lower for x in ("create", "save", "insert", "add", "new", "make", "build")):
            if model_lower in name_lower or model_lower in sig.lower():
                return True
        return False

    def _is_reader(self, row, model_name: str, sig: str) -> bool:
        """Heuristic: does this function read/consume the model?"""
        name_lower = row["name"].lower()
        model_lower = model_name.lower()
        # Parameter type annotation contains model
        if f": {model_name}" in sig or f": list[{model_name}" in sig.lower():
            return True
        # Function name suggests reading
        if any(x in name_lower for x in ("get", "read", "fetch", "find", "list", "load", "parse")):
            if model_lower in name_lower or model_lower in sig.lower():
                return True
        return False
