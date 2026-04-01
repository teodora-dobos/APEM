from collections.abc import Hashable
from typing import Any

import networkx as nx
import numpy as np


def compute_node_degree_centrality(G: nx.Graph) -> dict[Hashable, float]:
    """
    Compute node degree centrality for all nodes.

    Degree centrality is degree divided by the maximum possible degree
    (`n - 1`), so values are in `[0, 1]`.
    """
    deg_centrality = nx.degree_centrality(G)
    return deg_centrality


def compute_node_betweenness_centrality(G: nx.Graph) -> dict[Hashable, float]:
    """
    Compute node betweenness centrality for all nodes.

    Betweenness centrality is the fraction of shortest paths between node
    pairs that pass through each node. This implementation is unweighted and
    normalized.
    """
    bet_centrality = nx.betweenness_centrality(G, weight=None, normalized=True)

    return bet_centrality


def compute_edge_betweenness(
    G: nx.Graph,
    weight: str | None = None,
    normalized: bool = True,
) -> dict[tuple[Hashable, Hashable], float]:
    """
    Compute edge betweenness centrality for all edges.

    Delegates to `networkx.edge_betweenness_centrality` with the provided
    `weight` and `normalized` options.
    """
    bet_centrality = nx.edge_betweenness_centrality(G, k=None, normalized=normalized, weight=weight)
    return bet_centrality


def compute_node_ptdf_contribution_scores(
    ptdf: np.ndarray,
    edges: list[tuple[Hashable, Hashable, dict[str, Any]]],
    nodes: list[Hashable],
    mask: list[int],
    G: nx.Graph,
    method: str = "sum",
    fmax_attr: str = "F_max",
) -> dict[Hashable, float]:
    """
    Compute PTDF-based node contribution scores.

    Parameters
    ----------
    ptdf : (m, n-1) np.ndarray
        PTDF rows=lines, cols=non-slack buses (order = `mask`).
    edges : list[(u, v, data)]
        Edges matching ptdf rows.
    nodes : list
        All node labels (order used to build B).
    mask : list[int]
        Indices of non-slack buses corresponding to ptdf columns.
    G : nx.Graph
        Graph with edge attribute fmax_attr.
    method : {"sum","max","weighted_sum"}
        - "sum":          sum_l |PTDF_{l,k}|
        - "max":          max_l |PTDF_{l,k}|
        - "weighted_sum": sum_l |PTDF_{l,k}| * F_max(l)
    fmax_attr : str
        Edge attribute used as weight for "weighted_sum".

    Returns
    -------
    scores : dict[node_label, score]
        Contribution score for each node. Slack node has score 0.
    """
    m, _ncols = ptdf.shape

    # Build weights per line if requested (otherwise set to 1)
    if method == "weighted_sum":
        weights = np.array([float(G[u][v].get(fmax_attr, 1.0)) for (u, v, _) in edges], dtype=float)
    else:
        weights = np.ones(m, dtype=float)

    # Absolute PTDF values (flow sensitivities can be positive/negative by convention)
    abs_ptdf = np.abs(ptdf)  # shape = (m, n-1)

    if method in ("sum", "weighted_sum"):
        # Sum over all lines, optionally weighted by line capacity
        scores_non_slack = (abs_ptdf * weights[:, None]).sum(axis=0)
    elif method == "max":
        # Take the maximum absolute PTDF per node
        scores_non_slack = abs_ptdf.max(axis=0)
    else:
        raise ValueError(f"Unknown method '{method}'.")

    # Place scores back into full node order (slack bus gets score 0)
    scores_full = np.zeros(len(nodes), dtype=float)
    scores_full[np.array(mask)] = scores_non_slack

    return {node: float(score) for node, score in zip(nodes, scores_full)}
