from collections.abc import Hashable
from typing import Any

import networkx as nx
import numpy as np

from node_ranking.graph_metrics import (
    compute_node_ptdf_contribution_scores,
    compute_node_betweenness_centrality,
    compute_node_degree_centrality,
)
from node_ranking.market_metrics import (
    dispatch_volume_score,
    gamma_capacity_score,
    gamma_capacity_congestion_score,
    load_weighted_lmp_score,
    ptdf_stress_score,
    rent_weighted_dispatch_score,
)


def _rank_scores_desc(scores: dict[Hashable, float]) -> list[tuple[Hashable, float]]:
    """
    Sort score dictionary descending by score value.
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
    Rank nodes by PTDF contribution score.
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
    """
    # Compute centrality scores (normalized to [0,1])
    deg_centrality = compute_node_degree_centrality(G)
    ranking = sorted(deg_centrality.items(), key=lambda x: -x[1])
    return ranking


def rank_nodes_by_betweenness(G: nx.Graph) -> list[tuple[Hashable, float]]:
    """
    Rank nodes by betweenness centrality.
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
    Rank nodes by shadow-margin score from baseline market outputs.
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
    Rank nodes by total dispatched generation in baseline market outputs.
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
    Rank nodes by gamma-capacity score from baseline market outputs.
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
    Rank nodes by scarcity score from baseline market outputs.
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
    Rank nodes by gamma-capacity-congestion score from baseline market outputs.
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
