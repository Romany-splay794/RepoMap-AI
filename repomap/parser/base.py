"""Base types for the parser layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable


class SymbolKind(StrEnum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    INTERFACE = "interface"
    MODEL = "model"       # data model (Pydantic, dataclass, TS interface)
    IMPORT = "import"     # import statement — used to build edges


@dataclass
class Symbol:
    """A single extracted symbol from a source file."""

    name: str
    qualified_name: str       # module.Class.method dotted path
    kind: SymbolKind
    file_path: Path
    line_start: int
    line_end: int
    signature: str = ""
    language: str = ""
    is_entry_point: bool = False
    is_exported: bool = True

    # Parser-layer extras (not persisted as columns, used for edge building)
    references: list[str] = field(default_factory=list)   # names this symbol calls/reads
    bases: list[str] = field(default_factory=list)        # class inheritance bases
    decorators: list[str] = field(default_factory=list)   # @decorator names
    imports: list[tuple[str, str]] = field(default_factory=list)  # [(module, name), ...]


@runtime_checkable
class BaseParser(Protocol):
    def parse(self, file_path: Path) -> list[Symbol]: ...
    def supports(self, file_path: Path) -> bool: ...
