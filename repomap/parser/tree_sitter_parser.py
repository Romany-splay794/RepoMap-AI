"""Tree-sitter based source parser for Python, TypeScript, JavaScript, Go, Java, Rust, C, C++, and Ruby."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from repomap.parser.base import Symbol, SymbolKind

# Language extension → tree-sitter language name
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".rb": "ruby",
}

# Module-level caches to avoid re-creating parsers/queries/languages per file
_parser_cache: dict[str, Any] = {}
_query_cache: dict[str, Any] = {}
_language_cache: dict[str, Any] = {}


def _get_language(lang_name: str) -> Any:
    if lang_name in _language_cache:
        return _language_cache[lang_name]
    try:
        import tree_sitter
        if lang_name == "python":
            import tree_sitter_python as tsp
            lang = tree_sitter.Language(tsp.language())
        elif lang_name in ("typescript", "tsx"):
            import tree_sitter_typescript as tsts
            lang = tree_sitter.Language(tsts.language_typescript())
        elif lang_name == "javascript":
            try:
                import tree_sitter_javascript as tsjs
                lang = tree_sitter.Language(tsjs.language())
            except ImportError:
                import tree_sitter_typescript as tsts
                lang = tree_sitter.Language(tsts.language_typescript())
        elif lang_name == "go":
            import tree_sitter_go as tsgo
            lang = tree_sitter.Language(tsgo.language())
        elif lang_name == "java":
            import tree_sitter_java as tsjava
            lang = tree_sitter.Language(tsjava.language())
        elif lang_name == "rust":
            import tree_sitter_rust as tsrust
            lang = tree_sitter.Language(tsrust.language())
        elif lang_name == "c":
            import tree_sitter_c as tsc
            lang = tree_sitter.Language(tsc.language())
        elif lang_name == "cpp":
            import tree_sitter_cpp as tscpp
            lang = tree_sitter.Language(tscpp.language())
        elif lang_name == "ruby":
            import tree_sitter_ruby as tsruby
            lang = tree_sitter.Language(tsruby.language())
        else:
            return None
        _language_cache[lang_name] = lang
        return lang
    except (ImportError, Exception):
        return None


def _get_parser(lang_name: str) -> Any:
    if lang_name in _parser_cache:
        return _parser_cache[lang_name]
    lang = _get_language(lang_name)
    if lang is None:
        return None
    try:
        import tree_sitter
        parser = tree_sitter.Parser(lang)
        _parser_cache[lang_name] = parser
        return parser
    except Exception:
        return None


def _get_query(lang_name: str) -> Any:
    cache_key = lang_name
    if cache_key in _query_cache:
        return _query_cache[cache_key]
    lang = _get_language(lang_name)
    if lang is None:
        return None

    # JavaScript uses TypeScript queries (compatible superset)
    query_lang = "typescript" if lang_name == "javascript" else lang_name
    scm_path = Path(__file__).parent / "queries" / f"{query_lang}.scm"
    if not scm_path.exists():
        return None
    try:
        import tree_sitter
        scm_text = scm_path.read_text(encoding="utf-8")
        query = tree_sitter.Query(lang, scm_text)
        _query_cache[cache_key] = query
        return query
    except Exception:
        return None


def _node_text(source: bytes, node: Any) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


_MAX_SIG_LEN = 120  # characters


def _extract_signature(source: bytes, node: Any) -> str:
    """Extract the function/method signature (name + params + return type), no body."""
    sig_end = node.end_byte
    for child in node.children:
        if child.type in ("block", "statement_block", "suite"):
            sig_end = child.start_byte
            break
    raw = source[node.start_byte:sig_end].decode("utf-8", errors="replace").strip()
    # Collapse newlines/extra whitespace within the signature
    sig = re.sub(r"\s+", " ", raw)
    if len(sig) > _MAX_SIG_LEN:
        sig = sig[:_MAX_SIG_LEN].rsplit(" ", 1)[0] + " ..."
    return sig


def _file_to_module(file_path: Path, repo_root: Path) -> str:
    """Convert file path to dotted module name relative to repo root."""
    try:
        rel = file_path.relative_to(repo_root)
    except ValueError:
        rel = file_path
    parts = list(rel.parts)
    if parts and parts[-1].endswith(
        (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs",
         ".go", ".java", ".rs", ".c", ".h", ".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".rb")
    ):
        parts[-1] = Path(parts[-1]).stem
    # Remove 'index' trailing component for TS/JS barrel files
    if parts and parts[-1] in ("index", "__init__"):
        parts = parts[:-1]
    return ".".join(parts) if parts else file_path.stem


class TreeSitterParser:
    """Parses source files into Symbol lists using tree-sitter grammars."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in EXTENSION_TO_LANGUAGE

    def parse(self, file_path: Path) -> list[Symbol]:
        lang_name = EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())
        if lang_name is None:
            return []
        parser = _get_parser(lang_name)
        if parser is None:
            return []
        query = _get_query(lang_name)
        if query is None:
            return []

        try:
            source = file_path.read_bytes()
        except OSError:
            return []

        try:
            tree = parser.parse(source)
        except Exception:
            return []

        try:
            import tree_sitter
            cursor = tree_sitter.QueryCursor(query)
            captures = cursor.captures(tree.root_node)
        except Exception:
            return []

        module_name = _file_to_module(file_path, self.repo_root)
        return self._build_symbols(captures, source, file_path, module_name, lang_name)

    def parse_string(self, code: str, language: str, file_path: Path | None = None) -> list[Symbol]:
        """Parse source code from a string (used in tests)."""
        fp = file_path or Path(f"<string>.{language[:2]}")
        parser = _get_parser(language)
        if parser is None:
            return []
        query = _get_query(language)
        if query is None:
            return []
        source = code.encode("utf-8")
        try:
            tree = parser.parse(source)
            import tree_sitter
            cursor = tree_sitter.QueryCursor(query)
            captures = cursor.captures(tree.root_node)
        except Exception:
            return []
        module_name = fp.stem
        return self._build_symbols(captures, source, fp, module_name, language)

    def _build_symbols(
        self,
        captures: dict[str, list],
        source: bytes,
        file_path: Path,
        module_name: str,
        lang_name: str,
    ) -> list[Symbol]:
        symbols: list[Symbol] = []

        # ── Collect class ranges for qualified name building ───────────────────
        # Maps class_name → (start_byte, end_byte)
        class_ranges: list[tuple[str, int, int]] = []
        for node in captures.get("def.class", []):
            name_nodes = captures.get("def.class.name", [])
            for nn in name_nodes:
                if node.start_byte <= nn.start_byte < node.end_byte:
                    class_ranges.append((
                        _node_text(source, nn),
                        node.start_byte,
                        node.end_byte,
                    ))
                    break

        # Rust/Go: build impl/receiver ranges so methods get qualified names
        # Go method_declaration has receiver param like "(s *Server)" → extract "Server"
        if lang_name == "go":
            for node in captures.get("def.method", []):
                recv_nodes = captures.get("def.method.receiver", [])
                for rn in recv_nodes:
                    if node.start_byte <= rn.start_byte < node.end_byte:
                        recv_text = _node_text(source, rn).strip("()")
                        # Extract type from "*Server" or "Server" or "s *Server"
                        parts = recv_text.split()
                        type_name = parts[-1].lstrip("*") if parts else ""
                        if type_name:
                            class_ranges.append((type_name, node.start_byte, node.end_byte))
                        break

        # Rust: impl blocks define the enclosing type for methods
        if lang_name == "rust":
            for node in captures.get("def.impl.type", []):
                impl_type = _node_text(source, node)
                # Find the parent impl_item node
                parent = node.parent
                if parent and parent.type == "impl_item":
                    class_ranges.append((impl_type, parent.start_byte, parent.end_byte))

        def enclosing_class(node: Any, exclude_self: bool = False) -> str | None:
            # Return innermost (smallest span) enclosing class for nested classes
            best: tuple[str, int] | None = None  # (name, span_size)
            for cname, cstart, cend in class_ranges:
                if cstart <= node.start_byte < cend:
                    # Skip exact match (the class itself)
                    if exclude_self and cstart == node.start_byte and cend == node.end_byte:
                        continue
                    span = cend - cstart
                    if best is None or span < best[1]:
                        best = (cname, span)
            return best[0] if best else None

        def make_qname(sym_name: str, node: Any) -> str:
            cls = enclosing_class(node)
            if cls:
                return f"{module_name}.{cls}.{sym_name}"
            return f"{module_name}.{sym_name}"

        # ── Collect call references (will be attached to enclosing functions) ──
        call_names: list[tuple[str, int]] = []  # (name, call_start_byte)
        for node in captures.get("ref.call.simple", captures.get("ref.call", [])):
            name_nodes = captures.get("ref.call.name", [])
            for nn in name_nodes:
                if abs(nn.start_byte - node.start_byte) < 200:
                    call_names.append((_node_text(source, nn), node.start_byte))
                    break
        # attr-style calls: obj.method()
        for node in captures.get("ref.call.attr", []):
            name_nodes = captures.get("ref.call.name", [])
            for nn in name_nodes:
                if abs(nn.start_byte - node.start_byte) < 200:
                    call_names.append((_node_text(source, nn), node.start_byte))
                    break

        def calls_within(fn_start: int, fn_end: int) -> list[str]:
            seen: set[str] = set()
            result: list[str] = []
            for name, pos in call_names:
                if fn_start <= pos < fn_end and name not in seen:
                    seen.add(name)
                    result.append(name)
            return result

        # ── Collect decorators ─────────────────────────────────────────────────
        # Maps decorator_start_byte → decorator text
        decorator_texts: list[tuple[int, str]] = []
        for node in captures.get("def.function.decorator", captures.get("def.method.decorator", [])):
            decorator_texts.append((node.start_byte, _node_text(source, node)))

        def decorators_before(fn_start: int) -> list[str]:
            return [
                txt for pos, txt in decorator_texts
                if fn_start - 200 <= pos < fn_start
            ]

        # ── Classes ────────────────────────────────────────────────────────────
        processed_class_bytes: set[tuple[int, int]] = set()
        for node in captures.get("def.class", []):
            key = (node.start_byte, node.end_byte)
            if key in processed_class_bytes:
                continue
            processed_class_bytes.add(key)

            name_nodes = [
                nn for nn in captures.get("def.class.name", [])
                if node.start_byte <= nn.start_byte < node.end_byte
            ]
            if not name_nodes:
                continue
            name = _node_text(source, name_nodes[0])

            # Bases
            bases: list[str] = []
            bases_node_list = captures.get("def.class.bases", [])
            for bn in bases_node_list:
                if node.start_byte <= bn.start_byte < node.end_byte:
                    # Extract individual base names from argument_list
                    raw = _node_text(source, bn).strip("()")
                    for base in re.split(r"[,\s]+", raw):
                        base = base.strip()
                        if base and base.isidentifier():
                            bases.append(base)

            # For classes, exclude self from enclosing_class lookup
            outer = enclosing_class(node, exclude_self=True)
            if outer:
                qname = f"{module_name}.{outer}.{name}"
            else:
                qname = f"{module_name}.{name}"
            sym = Symbol(
                name=name,
                qualified_name=qname,
                kind=SymbolKind.CLASS,
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=f"class {name}" + (f"({', '.join(bases)})" if bases else ""),
                language=lang_name,
                bases=bases,
                decorators=decorators_before(node.start_byte),
                references=calls_within(node.start_byte, node.end_byte),
            )
            symbols.append(sym)

        # Single dedup set keyed on (start_byte, end_byte) — covers functions, methods, arrows
        processed_fn_bytes: set[tuple[int, int]] = set()

        # ── Methods first (so they claim their byte ranges before top-level functions) ──
        for node in captures.get("def.method", []):
            key = (node.start_byte, node.end_byte)
            if key in processed_fn_bytes:
                continue
            processed_fn_bytes.add(key)
            self._add_function_symbol(
                node, captures, source, file_path, lang_name, module_name,
                enclosing_class, calls_within, decorators_before, symbols,
                kind=SymbolKind.METHOD,
            )

        # ── Top-level functions (skip any already claimed by method pass) ─────
        for node in captures.get("def.function", []):
            key = (node.start_byte, node.end_byte)
            if key in processed_fn_bytes:
                continue
            processed_fn_bytes.add(key)
            self._add_function_symbol(
                node, captures, source, file_path, lang_name, module_name,
                enclosing_class, calls_within, decorators_before, symbols,
                kind=SymbolKind.FUNCTION,
            )

        # Decorated functions (find inner function_definition, skip if already processed)
        for node in captures.get("def.function.decorated", []):
            inner_fn = None
            for child in node.children:
                if child.type == "function_definition":
                    inner_fn = child
                    break
            if inner_fn is None:
                continue
            key = (inner_fn.start_byte, inner_fn.end_byte)
            if key in processed_fn_bytes:
                continue
            processed_fn_bytes.add(key)
            self._add_function_symbol(
                inner_fn, captures, source, file_path, lang_name, module_name,
                enclosing_class, calls_within, decorators_before, symbols,
                kind=SymbolKind.FUNCTION,
            )

        # Arrow functions
        for node in captures.get("def.function.arrow", []):
            key = (node.start_byte, node.end_byte)
            if key in processed_fn_bytes:
                continue
            processed_fn_bytes.add(key)
            # node is a variable_declarator; find the identifier name
            name_nodes = [
                nn for nn in captures.get("def.function.name", [])
                if node.start_byte <= nn.start_byte < node.end_byte
            ]
            if not name_nodes:
                continue
            name = _node_text(source, name_nodes[0])
            qname = make_qname(name, node)
            sym = Symbol(
                name=name,
                qualified_name=qname,
                kind=SymbolKind.FUNCTION,
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=f"const {name} = (...) => ...",
                language=lang_name,
                references=calls_within(node.start_byte, node.end_byte),
            )
            symbols.append(sym)

        # ── Interfaces (TypeScript) ────────────────────────────────────────────
        for node in captures.get("def.interface", []):
            name_nodes = [
                nn for nn in captures.get("def.interface.name", [])
                if node.start_byte <= nn.start_byte < node.end_byte
            ]
            if not name_nodes:
                continue
            name = _node_text(source, name_nodes[0])
            qname = f"{module_name}.{name}"
            sym = Symbol(
                name=name,
                qualified_name=qname,
                kind=SymbolKind.INTERFACE,
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=f"interface {name}",
                language=lang_name,
                is_exported=True,
            )
            symbols.append(sym)

        # ── Imports ────────────────────────────────────────────────────────────
        import_list: list[tuple[str, str]] = []
        # Python: import foo.bar
        for node in captures.get("ref.import", []):
            mod_nodes = captures.get("ref.import.module", [])
            for mn in mod_nodes:
                if abs(mn.start_byte - node.start_byte) < 100:
                    import_list.append((_node_text(source, mn), "*"))
        # Python: from foo import bar
        for node in captures.get("ref.import.from", []):
            from_nodes = captures.get("ref.import.from_module", [])
            name_nodes_ = captures.get("ref.import.name", [])
            module = ""
            for mn in from_nodes:
                if abs(mn.start_byte - node.start_byte) < 100:
                    module = _node_text(source, mn)
                    break
            for nn in name_nodes_:
                if abs(nn.start_byte - node.start_byte) < 100:
                    import_list.append((module, _node_text(source, nn)))
        # TS/JS: import ... from "source"
        for node in captures.get("ref.import.named", []):
            src_nodes = captures.get("ref.import.source", [])
            name_nodes_ = captures.get("ref.import.name", [])
            module = ""
            for sn in src_nodes:
                if abs(sn.start_byte - node.start_byte) < 100:
                    module = _node_text(source, sn).strip("\"'")
                    break
            for nn in name_nodes_:
                if abs(nn.start_byte - node.start_byte) < 100:
                    import_list.append((module, _node_text(source, nn)))

        # Attach imports to a synthetic file-level symbol if any exist
        if import_list:
            sym = Symbol(
                name=f"<imports:{module_name}>",
                qualified_name=f"{module_name}.__imports__",
                kind=SymbolKind.IMPORT,
                file_path=file_path,
                line_start=1,
                line_end=1,
                language=lang_name,
                imports=import_list,
            )
            symbols.append(sym)

        # Final deduplication by (qualified_name, line_start) to handle any
        # remaining duplicates from overlapping query patterns
        seen_qname_line: set[tuple[str, int]] = set()
        unique: list[Symbol] = []
        for sym in symbols:
            key = (sym.qualified_name, sym.line_start)
            if key not in seen_qname_line:
                seen_qname_line.add(key)
                unique.append(sym)
        return unique

    def _add_function_symbol(
        self,
        node: Any,
        captures: dict,
        source: bytes,
        file_path: Path,
        lang_name: str,
        module_name: str,
        enclosing_class,
        calls_within,
        decorators_before,
        symbols: list[Symbol],
        kind: SymbolKind,
    ) -> None:
        # Check both function and method name captures
        all_name_nodes = captures.get("def.function.name", []) + captures.get("def.method.name", [])
        name_nodes = [
            nn for nn in all_name_nodes
            if node.start_byte <= nn.start_byte < node.end_byte
        ]
        if not name_nodes:
            return
        name = _node_text(source, name_nodes[0])
        cls = enclosing_class(node)
        if cls:
            qname = f"{module_name}.{cls}.{name}"
            sym_kind = SymbolKind.METHOD
        else:
            qname = f"{module_name}.{name}"
            sym_kind = kind

        sig = _extract_signature(source, node)
        decs = decorators_before(node.start_byte)
        refs = calls_within(node.start_byte, node.end_byte)

        # Detect entry points from decorator/annotation names
        is_entry = False
        for dec in decs:
            dec_lower = dec.lower()
            if any(x in dec_lower for x in ("route", "@get", "@post", "@put", "@delete", "@patch",
                                              ".get(", ".post(", ".put(", ".delete(", ".patch(")):
                is_entry = True
                break
            if "command" in dec_lower or "cli" in dec_lower:
                is_entry = True
                break
            # Java Spring annotations
            if any(x in dec_lower for x in ("getmapping", "postmapping", "putmapping",
                                              "deletemapping", "requestmapping",
                                              "restcontroller")):
                is_entry = True
                break
            # Rust web framework macros
            if any(x in dec_lower for x in ("#[get(", "#[post(", "#[put(",
                                              "#[delete(", "actix", "rocket",
                                              "tokio::main")):
                is_entry = True
                break
        if name == "main":
            is_entry = True

        sym = Symbol(
            name=name,
            qualified_name=qname,
            kind=sym_kind,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=sig,
            language=lang_name,
            is_entry_point=is_entry,
            decorators=decs,
            references=refs,
        )
        symbols.append(sym)
