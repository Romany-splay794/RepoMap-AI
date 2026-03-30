"""In-memory graph model types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EdgeType(StrEnum):
    CALLS = "calls"
    IMPORTS = "imports"
    READS = "reads"
    WRITES = "writes"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"


@dataclass
class GraphNode:
    symbol_id: int
    qualified_name: str
    name: str
    kind: str
    file_path: str
    line_start: int
    line_end: int
    signature: str
    language: str
    is_entry_point: bool
    is_exported: bool
    pagerank: float = 0.0
    is_hot_path: bool = False
    narrative: str = ""
    # Data model fields (populated after detection)
    data_model_framework: str | None = None
    data_model_fields: list[dict] = field(default_factory=list)


@dataclass
class GraphEdge:
    id: int
    source_id: int
    target_id: int | None
    source_qualified_name: str
    target_qualified_name: str
    edge_type: EdgeType
    confidence: float = 1.0

    @property
    def is_resolved(self) -> bool:
        return self.target_id is not None

    @property
    def display_arrow(self) -> str:
        return "→" if self.confidence >= 0.9 else "?→"
