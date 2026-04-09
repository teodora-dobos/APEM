"""High-level helpers for producing sorted node rankings.

This module wraps the lower-level score functions from ``network_scores`` and
``market_scores`` and converts raw score dictionaries into descending
``[(node, score), ...]`` rankings.
"""

from collections.abc import Hashable
from typing import Any

import networkx as nx
import numpy as np

from node_ranking.network_scores import (
    compute_node_ptdf_contribution_scores,
    compute_node_betweenness_centrality,
    compute_node_degree_centrality,
)
from node_ranking.market_scores import (
    dispatch_volume_score,
    gamma_capacity_score,
    gamma_capacity_congestion_score,
    load_weighted_lmp_score,
    ptdf_stress_score,
    rent_weighted_dispatch_score,
)


def _rank_scores_desc(scores: dict[Hashable, float]) -> list[tuple[Hashable, float]]:
    """
    Sort a node-score mapping in descending order.

    Parameters
    ----------
    scores : dict[hashable, float]
        Mapping from node label to score.

    Returns
    -------
    list[tuple[hashable, float]]
        ``(node, score)`` pairs sorted from highest to lowest score.
    """
    return sorted(scores.items(), key=lambda x: -x[1])


def rank_nodes_by_ptdf(
    ptdf: np.ndarray,
    edges: list[tuple[Hashable, Hashable, dict[str, Any]]],
    nodes: list[Hashable],
    mask: list[int],
    G: nx.Graph,
    method: str = "sum",
    fmax_attr: str = "F_max",
) -> list[tuple[Hashable, float]]:
    """
    Rank nodes by PTDF-contribution score.

    This is a thin wrapper around
    :func:`node_ranking.network_scores.compute_node_ptdf_contribution_scores`.
    It computes one PTDF-based score per node and returns the nodes sorted from
    most to least exposed according to the selected aggregation rule.

    Parameters
    ----------
    ptdf : np.ndarray
        PTDF matrix with rows as lines and columns as non-slack buses.
    edges : list[tuple]
        Edge list in the same order as the PTDF rows.
    nodes : list[hashable]
        Full node list used when constructing the PTDF.
    mask : list[int]
        Indices of the non-slack buses corresponding to PTDF columns.
    G : nx.Graph
        Network graph containing the line attributes used for scoring.
    method : {"sum", "max", "weighted_sum"}, default="sum"
        Aggregation rule used to collapse each PTDF column into a node score.
    fmax_attr : str, default="F_max"
        Edge attribute used as the line-capacity weight for
        ``method="weighted_sum"``.

    Returns
    -------
    list[tuple[hashable, float]]
        Sorted ``(node, score)`` pairs.
    """
    scores = compute_node_ptdf_contribution_scores(
        ptdf=ptdf,
        edges=edges,
        nodes=nodes,
        mask=mask,
        G=G,
        method=method,
        fmax_attr=fmax_attr,
    )
    return sorted(scores.items(), key=lambda x: -x[1])


def rank_nodes_by_degree(G: nx.Graph) -> list[tuple[Hashable, float]]:
    """
    Rank nodes by degree centrality.

    This ranking is based on the node-level scores returned by
    :func:`node_ranking.network_scores.compute_node_degree_centrality`.

    Parameters
    ----------
    G : nx.Graph
        Input network.

    Returns
    -------
    list[tuple[hashable, float]]
        Sorted ``(node, score)`` pairs, where the score is the normalized
        degree centrality from NetworkX.
    """
    # Compute centrality scores (normalized to [0,1])
    deg_centrality = compute_node_degree_centrality(G)
    ranking = sorted(deg_centrality.items(), key=lambda x: -x[1])
    return ranking


def rank_nodes_by_betweenness(G: nx.Graph) -> list[tuple[Hashable, float]]:
    """
    Rank nodes by betweenness centrality.

    This ranking is based on the node-level scores returned by
    :func:`node_ranking.network_scores.compute_node_betweenness_centrality`.

    Parameters
    ----------
    G : nx.Graph
        Input network.

    Returns
    -------
    list[tuple[hashable, float]]
        Sorted ``(node, score)`` pairs, where the score is the normalized
        betweenness centrality from NetworkX.
    """
    bet_centrality = compute_node_betweenness_centrality(G)
    ranking = sorted(bet_centrality.items(), key=lambda x: -x[1])
    return ranking


def rank_nodes_by_shadow_score(
    nodes: dict[str, dict[str, float]],
    generators: dict[str, dict[str, float | str]],
    baseline_result: dict[str, dict[str, float]],
) -> list[tuple[Hashable, float]]:
    """
    Rank nodes by rent-weighted dispatch score.

    This ranking is based on the node-level scores returned by
    :func:`node_ranking.market_scores.rent_weighted_dispatch_score`.

    Parameters
    ----------
    nodes : dict
        Node data keyed by node label.
    generators : dict
        Generator data keyed by generator id.
    baseline_result : dict
        Baseline dispatch outputs containing at least ``dispatch`` and
        ``lambdas``.

    Returns
    -------
    list[tuple[hashable, float]]
        Sorted ``(node, score)`` pairs.
    """
    node_scores, _ = rent_weighted_dispatch_score(
        nodes=nodes,
        generators=generators,
        baseline_result=baseline_result,
    )
    return _rank_scores_desc(node_scores)


def rank_nodes_by_dispatch_volume(
    nodes: dict[str, dict[str, float]],
    generators: dict[str, dict[str, float | str]],
    baseline_result: dict[str, dict[str, float]],
) -> list[tuple[Hashable, float]]:
    """
    Rank nodes by dispatched generation volume.

    This ranking is based on the node-level scores returned by
    :func:`node_ranking.market_scores.dispatch_volume_score`.

    Parameters
    ----------
    nodes : dict
        Node data keyed by node label.
    generators : dict
        Generator data keyed by generator id.
    baseline_result : dict
        Baseline dispatch outputs containing ``dispatch``.

    Returns
    -------
    list[tuple[hashable, float]]
        Sorted ``(node, score)`` pairs.
    """
    node_scores = dispatch_volume_score(
        nodes=nodes,
        generators=generators,
        baseline_result=baseline_result,
    )
    return _rank_scores_desc(node_scores)


def rank_nodes_by_gamma_capacity_score(
    nodes: dict[str, dict[str, float]],
    generators: dict[str, dict[str, float | str]],
    baseline_result: dict[str, dict[str, float]],
) -> list[tuple[Hashable, float]]:
    """
    Rank nodes by gamma-capacity score.

    This ranking is based on the node-level scores returned by
    :func:`node_ranking.market_scores.gamma_capacity_score`.

    Parameters
    ----------
    nodes : dict
        Node data keyed by node label.
    generators : dict
        Generator data keyed by generator id.
    baseline_result : dict
        Baseline dispatch outputs containing ``gamma``.

    Returns
    -------
    list[tuple[hashable, float]]
        Sorted ``(node, score)`` pairs.
    """
    node_scores, _ = gamma_capacity_score(
        nodes=nodes,
        generators=generators,
        baseline_result=baseline_result,
    )
    return _rank_scores_desc(node_scores)


def rank_nodes_by_scarcity_score(
    nodes: dict[str, dict[str, float]],
    baseline_result: dict[str, dict[str, float]],
    VOLL: float = 500.0,
    cap_lambda: bool = True,
) -> list[tuple[Hashable, float]]:
    """
    Rank nodes by load-weighted LMP scarcity score.

    This ranking is based on nodal prices, node load, and an optional VOLL
    cap applied to prices before scoring.
    It uses the node-level scores returned by
    :func:`node_ranking.market_scores.load_weighted_lmp_score`.

    Parameters
    ----------
    nodes : dict
        Node data keyed by node label. Each node must provide ``load``.
    baseline_result : dict
        Baseline dispatch outputs containing ``lambdas``.
    VOLL : float, default=500.0
        Value of lost load used as the optional price cap.
    cap_lambda : bool, default=True
        Whether to cap nodal prices at ``VOLL`` before scoring.

    Returns
    -------
    list[tuple[hashable, float]]
        Sorted ``(node, score)`` pairs.
    """
    node_scores = load_weighted_lmp_score(
        nodes=nodes,
        baseline_result=baseline_result,
        VOLL=VOLL,
        cap_lambda=cap_lambda,
    )
    return _rank_scores_desc(node_scores)


def rank_nodes_by_gamma_capacity_congestion_score(
    nodes: dict[str, dict[str, float]],
    generators: dict[str, dict[str, float | str]],
    lines: dict[str, dict[str, float | tuple[str, str]]],
    baseline_result: dict[str, dict[str, float]],
) -> list[tuple[Hashable, float]]:
    """
    Rank nodes by gamma-capacity-congestion score.

    This ranking is based on the node-level scores returned by
    :func:`node_ranking.market_scores.gamma_capacity_congestion_score`.

    Parameters
    ----------
    nodes : dict
        Node data keyed by node label.
    generators : dict
        Generator data keyed by generator id.
    lines : dict
        Line data keyed by line id.
    baseline_result : dict
        Baseline dispatch outputs containing ``gamma``, ``mu_plus``, and
        ``mu_minus``.

    Returns
    -------
    list[tuple[hashable, float]]
        Sorted ``(node, score)`` pairs.
    """
    node_scores = gamma_capacity_congestion_score(
        nodes=nodes,
        generators=generators,
        lines=lines,
        baseline_result=baseline_result,
    )
    return _rank_scores_desc(node_scores)


def rank_nodes_by_ptdf_stress_score(
    ptdf: np.ndarray,
    nodes: list[Hashable],
    mask: list[int],
    generators: dict[str, dict[str, float | str]],
    line_margins: np.ndarray | list[float],
    epsilon: float = 1e-6,
) -> list[tuple[Hashable, float]]:
    """
    Rank nodes by PTDF stress score.

    This ranking is based on the node-level scores returned by
    :func:`node_ranking.market_scores.ptdf_stress_score`.

    Parameters
    ----------
    ptdf : np.ndarray
        PTDF matrix with rows as lines and columns as non-slack buses.
    nodes : list[hashable]
        Full node list used when constructing the PTDF.
    mask : list[int]
        Indices of the non-slack buses corresponding to PTDF columns.
    generators : dict
        Generator data keyed by generator id.
    line_margins : np.ndarray or list[float]
        Residual margin for each PTDF row / line.
    epsilon : float, default=1e-6
        Small positive stabilizer added to the denominator.

    Returns
    -------
    list[tuple[hashable, float]]
        Sorted ``(node, score)`` pairs.
    """
    scores = ptdf_stress_score(
        ptdf=ptdf,
        nodes=nodes,
        mask=mask,
        generators=generators,
        line_margins=line_margins,
        epsilon=epsilon,
    )
    return _rank_scores_desc(scores)
