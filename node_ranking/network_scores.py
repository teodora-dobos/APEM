"""Topology-based score functions for node-ranking workflows.

The functions in this module operate directly on the network representation or
on precomputed PTDF data. They do not require an economic-dispatch solution.
"""

from collections.abc import Hashable
from typing import Any

import networkx as nx
import numpy as np


def compute_node_degree_centrality(G: nx.Graph) -> dict[Hashable, float]:
    """
    Compute node degree centrality for all nodes.

    Degree centrality is the node degree divided by the maximum possible
    degree, ``n - 1``, so scores lie in ``[0, 1]`` for simple graphs.

    Parameters
    ----------
    G : nx.Graph
        Input network.

    Returns
    -------
    dict[hashable, float]
        Mapping from node label to normalized degree centrality.
    """
    deg_centrality = nx.degree_centrality(G)
    return deg_centrality


def compute_node_betweenness_centrality(G: nx.Graph) -> dict[Hashable, float]:
    """
    Compute node betweenness centrality for all nodes.

    Betweenness centrality is the fraction of shortest paths between node
    pairs that pass through each node. This implementation is unweighted and
    normalized.

    Parameters
    ----------
    G : nx.Graph
        Input network.

    Returns
    -------
    dict[hashable, float]
        Mapping from node label to normalized betweenness centrality.
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

    Parameters
    ----------
    G : nx.Graph
        Input network.
    weight : str or None, default=None
        Optional edge-attribute name used as a shortest-path weight. If
        ``None``, the graph is treated as unweighted.
    normalized : bool, default=True
        Whether to return normalized centrality values.

    Returns
    -------
    dict[tuple[hashable, hashable], float]
        Mapping from edge endpoints to edge-betweenness score.
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

    Each non-slack node receives a score based on the magnitude of its PTDF
    column across all lines. The score can be aggregated by sum, by maximum
    line impact, or by a capacity-weighted sum. The slack node is assigned
    score 0 because PTDF columns are only defined for the non-slack buses in
    the reduced representation.

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
        - "sum":          sum_l abs(PTDF_{l,k})
        - "max":          max_l abs(PTDF_{l,k})
        - "weighted_sum": sum_l abs(PTDF_{l,k}) * F_max(l)
    fmax_attr : str
        Edge attribute used as weight for "weighted_sum".

    Returns
    -------
    scores : dict[node_label, score]
        Contribution score for each node in the full node set. Slack node has
        score 0.
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
