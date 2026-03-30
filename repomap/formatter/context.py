"""Token-budget-aware context assembler using binary search."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from repomap.graph.models import GraphEdge, GraphNode

if TYPE_CHECKING:
    pass


class Formatter(Protocol):
    def render(self, nodes: list[GraphNode], edges: list[GraphEdge], total: int) -> str: ...


class ContextAssembler:
    """Binary-searches over PageRank-sorted nodes to fit the token budget."""

    def __init__(self, model: str = "gpt-4o") -> None:
        self._model = model
        self._enc = None

    def _get_enc(self):
        if self._enc is None:
            try:
                import tiktoken
                self._enc = tiktoken.encoding_for_model(self._model)
            except Exception:
                self._enc = None
        return self._enc

    def count_tokens(self, text: str) -> int:
        enc = self._get_enc()
        if enc is None:
            return len(text) // 4  # fallback: ~4 chars per token
        return len(enc.encode(text))

    def assemble(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        formatter: Formatter,
        max_tokens: int = 1000,
    ) -> tuple[str, int, int]:
        """
        Find the largest prefix of nodes (by pagerank) that fits in max_tokens.

        Returns: (rendered_text, tokens_used, total_symbols)
        """
        # Sort by pagerank descending; entry points get a boost
        def sort_key(n: GraphNode) -> float:
            score = n.pagerank
            if n.is_entry_point:
                score += 0.1
            return score

        sorted_nodes = sorted(nodes, key=sort_key, reverse=True)
        total = len(sorted_nodes)

        if total == 0:
            text = formatter.render([], [], 0)
            return text, self.count_tokens(text), 0

        # Quick check: does everything fit?
        full_text = formatter.render(sorted_nodes, edges, total)
        if self.count_tokens(full_text) <= max_tokens:
            return full_text, self.count_tokens(full_text), total

        # Binary search for the largest fitting prefix
        lo, hi = 1, total
        best_text = ""
        best_tokens = 0
        best_count = 0

        while lo <= hi:
            mid = (lo + hi) // 2
            candidate_nodes = sorted_nodes[:mid]
            candidate_ids = {n.symbol_id for n in candidate_nodes}
            candidate_edges = [
                e for e in edges
                if e.source_id in candidate_ids
                and (e.target_id is None or e.target_id in candidate_ids)
            ]
            text = formatter.render(candidate_nodes, candidate_edges, total)
            tokens = self.count_tokens(text)
            if tokens <= max_tokens:
                best_text = text
                best_tokens = tokens
                best_count = mid
                lo = mid + 1
            else:
                hi = mid - 1

        if not best_text:
            # At minimum render just the first symbol
            first = sorted_nodes[:1]
            best_text = formatter.render(first, [], total)
            best_tokens = self.count_tokens(best_text)
            best_count = 1

        return best_text, best_tokens, total
