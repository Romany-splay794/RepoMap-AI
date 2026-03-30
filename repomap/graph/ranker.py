"""PageRank-based relevance ranker."""

from __future__ import annotations

from repomap.graph.models import GraphNode


class GraphRanker:
    def rank(
        self,
        graph,   # nx.DiGraph
        personalization: dict[str, float] | None = None,
        alpha: float = 0.85,
    ) -> dict[str, float]:
        """Run personalized PageRank on a NetworkX DiGraph.

        Returns a map of qualified_name → pagerank score.
        """
        import networkx as nx

        if len(graph) == 0:
            return {}

        try:
            # Use the pure-Python implementation to avoid requiring scipy/numpy
            from networkx.algorithms.link_analysis.pagerank_alg import _pagerank_python
            scores = _pagerank_python(
                graph,
                alpha=alpha,
                personalization=personalization,
                max_iter=200,
                tol=1.0e-6,
            )
            return scores
        except nx.PowerIterationFailedConvergence:
            # Fall back to uniform scores
            n = len(graph)
            return {node: 1.0 / n for node in graph.nodes()}
        except Exception:
            # Final fallback: uniform distribution
            n = len(graph)
            return {node: 1.0 / n for node in graph.nodes()} if n else {}

    def build_personalization(
        self,
        target_qname: str,
        graph,
        boost_neighbors: bool = True,
    ) -> dict[str, float]:
        """Build a personalization dict centered on target_qname."""
        personalization: dict[str, float] = {}
        if target_qname not in graph:
            return {}
        personalization[target_qname] = 1.0
        if boost_neighbors:
            for neighbor in graph.neighbors(target_qname):
                personalization[neighbor] = personalization.get(neighbor, 0) + 0.5
            for predecessor in graph.predecessors(target_qname):
                personalization[predecessor] = personalization.get(predecessor, 0) + 0.5
        return personalization

    def apply_scores(self, nodes: list[GraphNode], scores: dict[str, float]) -> None:
        """Write PageRank scores back into GraphNode objects in place."""
        for node in nodes:
            node.pagerank = scores.get(node.qualified_name, 0.0)
