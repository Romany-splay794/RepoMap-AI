"""RepoMap engine — the main orchestrator."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from repomap.core.config import RepomapConfig
from repomap.core.symbol_store import SymbolStore
from repomap.data_models.detector import DataModelDetector
from repomap.data_models.tracker import DataModelTracker
from repomap.formatter.context import ContextAssembler
from repomap.formatter.json_fmt import JSONFormatter
from repomap.formatter.markdown import MarkdownFormatter
from repomap.formatter.xml_fmt import XMLFormatter
from repomap.graph.backends.networkx_backend import build_nx_graph
from repomap.graph.builder import GraphBuilder
from repomap.graph.ranker import GraphRanker
from repomap.graph.resolver import ReferenceResolver
from repomap.parser.fallback import FallbackParser
from repomap.parser.tree_sitter_parser import EXTENSION_TO_LANGUAGE, TreeSitterParser


@dataclass
class GenerationResult:
    text: str
    tokens_used: int
    total_symbols: int
    symbols_shown: int
    files_parsed: int
    files_stale: int
    stats: dict


class RepomapEngine:
    def __init__(self, repo_root: Path, config: RepomapConfig) -> None:
        self.repo_root = repo_root.resolve()
        self.config = config
        db_path = config.db_path
        if not db_path.is_absolute():
            db_path = self.repo_root / db_path
        self.store = SymbolStore(db_path)
        self._ts_parser = TreeSitterParser(self.repo_root)
        self._fallback_parser = FallbackParser()

    def generate(
        self,
        scope: Path | None = None,
        around: str | None = None,
        max_tokens: int | None = None,
        output_format: str | None = None,
        narratives: bool = False,
        hot_paths: bool = False,
        prepend: bool = False,
        enrich: str | None = None,
    ) -> GenerationResult:
        """Full pipeline: discover → parse → graph → rank → format."""
        budget = max_tokens or self.config.max_tokens
        fmt = output_format or self.config.output_format

        # 1. File discovery
        target_dir = (scope or self.repo_root).resolve()
        all_files = self._discover_files(target_dir)

        # 2. Incremental parse
        stale_files = self.store.get_stale_files(all_files)
        parsed_count = 0
        for fp in stale_files:
            if self._ts_parser.supports(fp):
                symbols = self._ts_parser.parse(fp)
            elif self.config.fallback_parser and self._fallback_parser.supports(fp):
                symbols = self._fallback_parser.parse(fp)
            else:
                continue
            if symbols:
                self.store.upsert_file_symbols(fp, symbols)
                parsed_count += 1

        # 3. Data model detection
        detector = DataModelDetector(self.store)
        detector.detect_and_store()

        # 4. Reference resolution
        resolver = ReferenceResolver(self.store, self.repo_root)
        resolver.resolve_all()

        # 5. Data model tracking (read/write edges)
        tracker = DataModelTracker(self.store)
        tracker.track()

        # 6. Build graph
        builder = GraphBuilder(self.store)
        if around:
            # Find nodes matching the around target
            seed_nodes = self._find_seeds(around)
            nodes, edges = builder.build_subgraph(seed_nodes, depth=2)
        else:
            nodes, edges = builder.build_from_store()

        if not nodes:
            assembler = ContextAssembler()
            formatter = self._get_formatter(fmt)
            text = formatter.render([], [], 0)
            return GenerationResult(
                text=text, tokens_used=assembler.count_tokens(text),
                total_symbols=0, symbols_shown=0,
                files_parsed=parsed_count, files_stale=len(stale_files),
                stats=self.store.stats(),
            )

        # 7. PageRank (tier-aware)
        tier = self._detect_tier(len(all_files))
        ranker = GraphRanker()
        personalization: dict | None = None

        if tier >= 2:
            scores = self._rank_scipy(nodes, edges, around)
        else:
            graph = build_nx_graph(nodes, edges)
            if around:
                seed_qnames = self._find_seeds(around)
                for qn in seed_qnames:
                    p = ranker.build_personalization(qn, graph)
                    if p:
                        personalization = p
                        break
            scores = ranker.rank(graph, personalization=personalization)
        ranker.apply_scores(nodes, scores)

        # 8. Intelligence layer (optional)
        if hot_paths:
            from repomap.intelligence.hot_paths import annotate_hot_paths, detect_hot_paths
            hot_ids = detect_hot_paths(nodes, edges)
            annotate_hot_paths(nodes, hot_ids)

        if narratives or enrich:
            from repomap.intelligence.narratives import generate_narratives
            narr = generate_narratives(nodes, edges)

            if enrich:
                narr = self._enrich_narratives(narr, nodes, enrich)

            # Attach narratives to nodes
            from pathlib import Path as P
            for node in nodes:
                mod_key = P(node.file_path).parts[0] if node.file_path else ""
                if mod_key in narr:
                    node.narrative = narr[mod_key]

        # 9. Format with token budget
        assembler = ContextAssembler()
        formatter = self._get_formatter(fmt)
        text, tokens_used, total = assembler.assemble(nodes, edges, formatter, budget)

        # Wrap in prepend mode if requested
        if prepend and fmt == "xml":
            from repomap.formatter.xml_fmt import XMLFormatter
            xml_fmt = XMLFormatter()
            text = xml_fmt.render_prepend(nodes, edges, total, repo_name=self.repo_root.name)

        return GenerationResult(
            text=text,
            tokens_used=tokens_used,
            total_symbols=total,
            symbols_shown=min(total, len(nodes)),
            files_parsed=parsed_count,
            files_stale=len(stale_files),
            stats=self.store.stats(),
        )

    def generate_all_formats(
        self,
        scope: Path | None = None,
        around: str | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, GenerationResult]:
        """Generate in all three formats, sharing one parse/graph pass."""
        budget = max_tokens or self.config.max_tokens

        all_files = self._discover_files((scope or self.repo_root).resolve())
        stale_files = self.store.get_stale_files(all_files)
        for fp in stale_files:
            if self._ts_parser.supports(fp):
                symbols = self._ts_parser.parse(fp)
            elif self.config.fallback_parser and self._fallback_parser.supports(fp):
                symbols = self._fallback_parser.parse(fp)
            else:
                continue
            if symbols:
                self.store.upsert_file_symbols(fp, symbols)

        DataModelDetector(self.store).detect_and_store()
        ReferenceResolver(self.store, self.repo_root).resolve_all()
        DataModelTracker(self.store).track()

        builder = GraphBuilder(self.store)
        nodes, edges = builder.build_from_store()
        graph = build_nx_graph(nodes, edges)
        ranker = GraphRanker()
        ranker.apply_scores(nodes, ranker.rank(graph))

        assembler = ContextAssembler()
        results: dict[str, GenerationResult] = {}
        for fmt_name, formatter in [
            ("markdown", MarkdownFormatter()),
            ("json", JSONFormatter()),
            ("xml", XMLFormatter()),
        ]:
            text, tokens, total = assembler.assemble(nodes, edges, formatter, budget)
            results[fmt_name] = GenerationResult(
                text=text, tokens_used=tokens, total_symbols=total,
                symbols_shown=len(nodes), files_parsed=len(stale_files),
                files_stale=len(stale_files), stats=self.store.stats(),
            )
        return results

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _detect_tier(self, file_count: int) -> int:
        if self.config.tier != "auto":
            return int(self.config.tier)
        if file_count < 1000:
            return 1
        elif file_count < 10000:
            return 2
        else:
            return 3

    def _discover_files(self, target_dir: Path) -> list[Path]:
        files: list[Path] = []
        try:
            for fp in target_dir.rglob("*"):
                if not fp.is_file():
                    continue
                rel = str(fp.relative_to(target_dir))
                if self._is_excluded(rel):
                    continue
                # Only parse files in configured languages + fallback
                if not (
                    self._ts_parser.supports(fp)
                    or (self.config.fallback_parser and self._fallback_parser.supports(fp))
                ):
                    continue
                files.append(fp)
        except PermissionError:
            pass
        return files

    def _is_excluded(self, rel_path: str) -> bool:
        for pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
            # Also match against just the path components
            if fnmatch.fnmatch("/" + rel_path, pattern):
                return True
        return False

    def _find_seeds(self, target: str) -> list[str]:
        """Find qualified names matching the around target."""
        results: list[str] = []
        # Exact qualified name
        row = self.store.get_symbol_by_qualified_name(target)
        if row:
            results.append(row["qualified_name"])
            return results
        # Short name match
        rows = self.store.get_symbols_by_name(target)
        for row in rows:
            results.append(row["qualified_name"])
        return results

    def _get_formatter(self, fmt: str):
        if fmt == "json":
            return JSONFormatter()
        elif fmt == "xml":
            return XMLFormatter()
        else:
            return MarkdownFormatter()

    def _rank_scipy(
        self,
        nodes: list,
        edges: list,
        around: str | None = None,
    ) -> dict:
        """Run PageRank via SciPy CSR backend (Tier 2+)."""
        try:
            from repomap.graph.backends.scipy_backend import build_scipy_graph
            sg = build_scipy_graph(nodes, edges)
            personalization: dict | None = None
            if around:
                seed_qnames = self._find_seeds(around)
                if seed_qnames:
                    seed = seed_qnames[0]
                    # Build personalization for seed + 1-hop neighbors
                    neighbors = {seed: 1.0}
                    for edge in edges:
                        if edge.source_qualified_name == seed:
                            neighbors[edge.target_qualified_name] = 0.5
                        elif edge.target_qualified_name == seed:
                            neighbors[edge.source_qualified_name] = 0.5
                    personalization = neighbors
            return sg.pagerank(personalization=personalization)
        except ImportError:
            # SciPy not installed — fall back to Tier 1
            from repomap.graph.backends.networkx_backend import build_nx_graph
            from repomap.graph.ranker import GraphRanker
            g = build_nx_graph(nodes, edges)
            return GraphRanker().rank(g)

    def _enrich_narratives(
        self,
        heuristic_narratives: dict[str, str],
        nodes: list,
        backend: str,
    ) -> dict[str, str]:
        """Replace heuristic narratives with LLM-generated ones."""
        try:
            from repomap.intelligence.llm_enrichment import LLMEnricher
        except ImportError:
            return heuristic_narratives

        enricher = LLMEnricher(
            backend=backend,
            cache_dir=self.repo_root / ".repomap",
        )
        try:
            from collections import defaultdict
            mod_syms: dict[str, list] = defaultdict(list)
            for n in nodes:
                from pathlib import Path as P
                mod = P(n.file_path).parts[0] if n.file_path else ""
                mod_syms[mod].append(n)

            enriched = {}
            for mod, heuristic in heuristic_narratives.items():
                syms = mod_syms.get(mod, [])
                names = [s.name for s in syms[:15]]
                sigs = [s.signature for s in syms if s.signature][:10]
                enriched[mod] = enricher.enrich_module_summary(
                    mod, names, sigs, heuristic
                )
            return enriched
        finally:
            enricher.close()

    def close(self) -> None:
        self.store.close()
