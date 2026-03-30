"""SciPy CSR sparse-matrix graph backend for Tier 2 repos (1K–10K files).

Implements power-iteration PageRank directly on a CSR matrix, bypassing
NetworkX's dict→CSR conversion which is the documented scaling wall.
"""

from __future__ import annotations

import numpy as np
from scipy import sparse

from repomap.graph.models import GraphEdge, GraphNode


class ScipyGraph:
    """Lightweight graph wrapper backed by a SciPy CSR matrix."""

    def __init__(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> None:
        self._nodes = nodes
        self._edges = edges
        # Build index mappings
        self._qname_to_idx: dict[str, int] = {
            n.qualified_name: i for i, n in enumerate(nodes)
        }
        self._idx_to_qname: dict[int, str] = {
            i: n.qualified_name for i, n in enumerate(nodes)
        }
        n = len(nodes)
        # Build COO data for CSR construction
        rows, cols, data = [], [], []
        for edge in edges:
            src = self._qname_to_idx.get(edge.source_qualified_name)
            tgt = self._qname_to_idx.get(edge.target_qualified_name)
            if src is not None and tgt is not None:
                rows.append(src)
                cols.append(tgt)
                data.append(edge.confidence)
        self.matrix: sparse.csr_matrix = sparse.csr_matrix(
            (data, (rows, cols)), shape=(n, n), dtype=np.float64
        )
        self.n = n

    def pagerank(
        self,
        alpha: float = 0.85,
        personalization: dict[str, float] | None = None,
        max_iter: int = 200,
        tol: float = 1.0e-6,
    ) -> dict[str, float]:
        """Power-iteration PageRank on the CSR matrix."""
        n = self.n
        if n == 0:
            return {}

        # Row-normalize the adjacency matrix (out-edges)
        A = self.matrix.copy().astype(np.float64)
        row_sums = np.array(A.sum(axis=1)).flatten()
        # Avoid division by zero for dangling nodes
        row_sums_safe = np.where(row_sums == 0, 1.0, row_sums)
        # Build D^{-1} A (row-stochastic)
        inv_diag = sparse.diags(1.0 / row_sums_safe)
        M = (inv_diag @ A).T  # column-stochastic for power iteration

        # Dangling nodes: rows with zero out-degree
        dangling_mask = (row_sums == 0).astype(np.float64)
        dangling_weights = dangling_mask / n  # distribute evenly

        # Personalization vector
        if personalization:
            v = np.zeros(n, dtype=np.float64)
            for qname, weight in personalization.items():
                idx = self._qname_to_idx.get(qname)
                if idx is not None:
                    v[idx] = weight
            v_sum = v.sum()
            if v_sum > 0:
                v /= v_sum
            else:
                v = np.ones(n, dtype=np.float64) / n
        else:
            v = np.ones(n, dtype=np.float64) / n

        # Initial distribution
        x = v.copy()

        for _ in range(max_iter):
            x_last = x.copy()
            # Dangling contribution
            dangling_sum = x_last @ dangling_mask
            # Power iteration step
            x = alpha * (M @ x_last + dangling_weights * dangling_sum) + (1 - alpha) * v
            # Convergence check (L1 norm)
            err = np.abs(x - x_last).sum()
            if err < n * tol:
                break

        return {self._idx_to_qname[i]: float(x[i]) for i in range(n)}


def build_scipy_graph(nodes: list[GraphNode], edges: list[GraphEdge]) -> ScipyGraph:
    return ScipyGraph(nodes, edges)
