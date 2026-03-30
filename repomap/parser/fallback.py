"""Regex-based fallback parser for languages without tree-sitter support."""

from __future__ import annotations

import re
from pathlib import Path

from repomap.parser.base import Symbol, SymbolKind

_PATTERNS: list[tuple[re.Pattern, SymbolKind]] = [
    # Python / Ruby
    (re.compile(r"^(?:async\s+)?def\s+(\w+)\s*[\(:]", re.MULTILINE), SymbolKind.FUNCTION),
    # Go
    (re.compile(r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(", re.MULTILINE), SymbolKind.FUNCTION),
    # Java / C# / Swift / Kotlin
    (re.compile(
        r"^\s*(?:public|private|protected|internal|static|override|virtual|async)?"
        r"(?:\s+(?:public|private|protected|static|override|virtual|async))*"
        r"\s+\w[\w<>\[\],\s]*\s+(\w+)\s*\(",
        re.MULTILINE,
    ), SymbolKind.FUNCTION),
    # Rust
    (re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*[<\(]", re.MULTILINE), SymbolKind.FUNCTION),
    # Classes (most languages)
    (re.compile(
        r"^(?:export\s+)?(?:abstract\s+)?(?:class|struct|interface|enum)\s+(\w+)",
        re.MULTILINE,
    ), SymbolKind.CLASS),
    # Arrow / const functions (JS/TS)
    (re.compile(
        r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(",
        re.MULTILINE,
    ), SymbolKind.FUNCTION),
]


class FallbackParser:
    """Regex-based heuristic parser for any language."""

    def supports(self, file_path: Path) -> bool:
        # Skip binary, documentation, and known non-code files
        return file_path.suffix.lower() not in {
            # Binary / media
            ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
            ".woff", ".woff2", ".ttf", ".eot",
            ".zip", ".tar", ".gz", ".pdf",
            # Package / lock files
            ".lock", ".sum",
            # Documentation / markup
            ".md", ".rst", ".txt", ".adoc", ".textile",
            # Config / data
            ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
            ".csv", ".sql", ".xml", ".html", ".css",
            # Compiled output
            ".pyc", ".pyo", ".class", ".o", ".a", ".so", ".dll", ".exe",
        }

    def parse(self, file_path: Path) -> list[Symbol]:
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        lines = source.splitlines()
        module_name = file_path.stem
        symbols: list[Symbol] = []
        seen: set[tuple[str, int]] = set()

        for pattern, kind in _PATTERNS:
            for m in pattern.finditer(source):
                name = m.group(1)
                line_no = source[: m.start()].count("\n") + 1
                key = (name, line_no)
                if key in seen:
                    continue
                seen.add(key)

                # Estimate line_end heuristically
                line_end = min(line_no + 30, len(lines))
                qname = f"{module_name}.{name}"
                sym = Symbol(
                    name=name,
                    qualified_name=qname,
                    kind=kind,
                    file_path=file_path,
                    line_start=line_no,
                    line_end=line_end,
                    language=file_path.suffix.lstrip("."),
                )
                symbols.append(sym)

        return symbols
