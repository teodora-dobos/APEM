"""Market-based score functions and PTDF utilities for node ranking.

This module contains:

- PTDF construction helpers for DC network representations
- node-level scores based on baseline dispatch outputs
- score formulations that use dispatch, nodal prices, scarcity duals, and
  congestion duals
"""

from collections.abc import Hashable
from typing import Any

import networkx as nx
import numpy as np


def build_B_matrix(
    G: nx.Graph,
    b_attr: str = "B",
) -> tuple[np.ndarray, list[Hashable], dict[Hashable, int]]:
    """
    Build the nodal susceptance (Laplacian) matrix for DC power flow.

    Parameters
    ----------
    G : nx.Graph
        Undirected graph with edge attribute `b_attr` = susceptance.
    b_attr : str
        Edge attribute name for susceptance.

    Returns
    -------
    B : (n, n) np.ndarray
        Nodal susceptance matrix.
    nodes : list
        Node labels in the order used for B.
    node_index : dict
        Map node label -> row/col index in B.

    Notes
    -----
    For each edge ``(u, v)``, the edge susceptance is added to the diagonal
    entries of ``u`` and ``v`` and subtracted from the corresponding
    off-diagonal entries.
    """
    nodes = list(G.nodes())
    n = len(nodes)
    node_index = {node: idx for idx, node in enumerate(nodes)}

    B = np.zeros((n, n), dtype=float)

    for u, v, data in G.edges(data=True):
        if b_attr not in data:
            raise KeyError(f"Edge ({u}, {v}) missing '{b_attr}' attribute.")
        b = float(data[b_attr])

        i, j = node_index[u], node_index[v]
        B[i, i] += b
        B[j, j] += b
        B[i, j] -= b
        B[j, i] -= b

    return B, nodes, node_index


def invert_reduced_B(
    B: np.ndarray,
    slack_idx: int,
) -> tuple[np.ndarray, list[int], np.ndarray]:
    """
    Invert the reduced B matrix after removing the slack row/column.

    Parameters
    ----------
    B : np.ndarray
        Full nodal susceptance matrix.
    slack_idx : int
        Index of the slack bus in ``B``.

    Returns
    -------
    Binv : (n-1, n-1) np.ndarray
        Inverse of the reduced B matrix.
    mask : list[int]
        Indices of non-slack buses kept in the reduced system.
    full2red : np.ndarray
        Map full-bus index -> reduced index (or -1 for slack).
    """
    n = B.shape[0]
    mask = [k for k in range(n) if k != slack_idx]
    Bred = B[np.ix_(mask, mask)]
    Binv = np.linalg.inv(Bred)

    full2red = np.full(n, -1, dtype=int)
    full2red[mask] = np.arange(n - 1)
    return Binv, mask, full2red


def compute_bus_angle_basis(
    Binv: np.ndarray,
    n: int,
    slack_idx: int,
    mask: list[int],
) -> np.ndarray:
    """
    Compute bus-angle responses for unit injections at non-slack buses.

    Parameters
    ----------
    Binv : np.ndarray
        Inverse of the reduced susceptance matrix.
    n : int
        Number of buses in the original full system.
    slack_idx : int
        Index of the slack bus in the full system. This argument is included
        for interface clarity; the slack angle is fixed implicitly by
        reinserting a zero row.
    mask : list[int]
        Full-system indices of the non-slack buses.

    Returns
    -------
    theta_full : (n, n-1) np.ndarray
        Voltage-angle responses with slack angle fixed at zero.
    """
    del slack_idx
    I = np.eye(n - 1)
    theta_red = Binv @ I

    theta_full = np.zeros((n, n - 1))
    theta_full[np.ix_(mask, np.arange(n - 1))] = theta_red
    return theta_full


def compute_ptdf(
    G: nx.Graph,
    slack: Hashable | None = None,
    b_attr: str = "B",
) -> tuple[np.ndarray, list[tuple[Hashable, Hashable, dict[str, Any]]], list[Hashable], list[int], Hashable]:
    """
    Compute the PTDF matrix (1 MW injection, slack withdrawal convention).

    Parameters
    ----------
    G : nx.Graph
        Network with line susceptance stored in ``b_attr``.
    slack : hashable or None, default=None
        Label of the slack node. If omitted, the first node in ``G.nodes()``
        is used.
    b_attr : str, default="B"
        Edge attribute containing line susceptance.

    Returns
    -------
    ptdf : (m, n-1) np.ndarray
        Rows = lines in `edges`, cols = non-slack buses (order = `mask`).
    edges : list[tuple]
        Edge list in the row order of `ptdf`.
    nodes : list
        Node labels in column/angle order used to build B.
    mask : list[int]
        Indices of non-slack buses (maps ptdf columns -> nodes[mask[c]]).
    slack_node : hashable
        The chosen slack node label.

    Notes
    -----
    The returned PTDF has one column per non-slack bus. Column ``c``
    corresponds to node ``nodes[mask[c]]``.
    """
    B, nodes, node_index = build_B_matrix(G, b_attr=b_attr)

    if slack is None:
        slack_node = nodes[0]
    else:
        slack_node = slack
        if slack_node not in node_index:
            raise ValueError(f"Slack node {slack_node} not in graph.")
    slack_idx = node_index[slack_node]

    Binv, mask, _ = invert_reduced_B(B, slack_idx)
    theta_full = compute_bus_angle_basis(Binv, n=len(nodes), slack_idx=slack_idx, mask=mask)

    edges = list(G.edges(data=True))
    m = len(edges)
    ncols = len(mask)
    ptdf = np.zeros((m, ncols))

    for row_idx, (u, v, data) in enumerate(edges):
        b = float(data[b_attr])
        iu, iv = node_index[u], node_index[v]
        ptdf[row_idx, :] = b * (theta_full[iu, :] - theta_full[iv, :])

    return ptdf, edges, nodes, mask, slack_node


def rent_weighted_dispatch_score(
    nodes: dict[str, dict[str, float]],
    generators: dict[str, dict[str, float | str]],
    baseline_result: dict[str, dict[str, float]],
) -> tuple[dict[str, float], dict[str, float]]:
    r"""
    Compute rent-weighted dispatch scores from a baseline dispatch.

    This score rewards dispatched generators that earn a positive gross margin
    at the baseline nodal price, then aggregates those generator-level scores
    to nodes.

    Score definition:

    .. math::
       s_g = \max(0, \lambda_{n(g)} - c_g)\, d_g

    .. math::
       S_v = \sum_{g \in G(v)} s_g

    where :math:`d_g` is dispatch, :math:`c_g` is generator cost, and
    :math:`\lambda_{n(g)}` is the nodal price at the generator's node.

    Parameters
    ----------
    nodes : dict
        Node data keyed by node label. Used to initialize the node-score map.
    generators : dict
        Generator data keyed by generator id. Each generator must provide at
        least ``node`` and ``cost``.
    baseline_result : dict
        Baseline dispatch outputs containing ``dispatch`` and ``lambdas``.

    Returns
    -------
    tuple[dict[str, float], dict[str, float]]
        ``(node_scores, gen_scores)`` with node-level and generator-level
        rent-weighted dispatch scores.
    """
    dispatch = baseline_result["dispatch"]
    lambdas = baseline_result["lambdas"]

    gen_scores: dict[str, float] = {}
    node_scores: dict[str, float] = {str(v): 0.0 for v in nodes}
    for g, data in generators.items():
        node = str(data["node"])
        lam = float(lambdas[node])
        margin = lam - float(data["cost"])
        score = max(0.0, margin) * float(dispatch[g])
        gen_scores[g] = score
        node_scores[node] = node_scores.get(node, 0.0) + score

    return node_scores, gen_scores


def dispatch_volume_score(
    nodes: dict[str, dict[str, float]],
    generators: dict[str, dict[str, float | str]],
    baseline_result: dict[str, dict[str, float]],
) -> dict[str, float]:
    r"""
    Compute node dispatch-volume scores from a baseline dispatch.

    This score is the total dispatched generation connected to each node.

    Score definition:

    .. math::
       S_v = \sum_{g \in G(v)} d_g

    Parameters
    ----------
    nodes : dict
        Node data keyed by node label.
    generators : dict
        Generator data keyed by generator id. Each generator must provide a
        ``node`` entry.
    baseline_result : dict
        Baseline dispatch outputs containing ``dispatch``.

    Returns
    -------
    dict[str, float]
        Node-level dispatch volume scores.
    """
    dispatch = baseline_result["dispatch"]
    node_scores: dict[str, float] = {str(v): 0.0 for v in nodes}
    for g, data in generators.items():
        node = str(data["node"])
        node_scores[node] = node_scores.get(node, 0.0) + float(dispatch.get(g, 0.0))

    return node_scores


def gamma_capacity_score(
    nodes: dict[str, dict[str, float]],
    generators: dict[str, dict[str, float | str]],
    baseline_result: dict[str, dict[str, float]],
) -> tuple[dict[str, float], dict[str, float]]:
    r"""
    Compute gamma-capacity scores from a baseline dispatch.

    This score combines the generator-capacity dual ``gamma`` with installed
    capacity and then aggregates the resulting generator-level scarcity signal
    to nodes.

    Score definition:

    .. math::
       s_g = \gamma_g P_g^{\max}

    .. math::
       S_v = \sum_{g \in G(v)} s_g

    Parameters
    ----------
    nodes : dict
        Node data keyed by node label.
    generators : dict
        Generator data keyed by generator id. Each generator must provide
        ``node`` and ``p_max``.
    baseline_result : dict
        Baseline dispatch outputs containing ``gamma``.

    Returns
    -------
    tuple[dict[str, float], dict[str, float]]
        ``(node_scores, gen_scores)`` with node-level and generator-level
        gamma-capacity scores.
    """
    gamma = baseline_result["gamma"]

    gen_scores: dict[str, float] = {}
    node_scores: dict[str, float] = {str(v): 0.0 for v in nodes}
    for g, data in generators.items():
        score = float(gamma[g]) * float(data["p_max"])
        gen_scores[g] = score
        node = str(data["node"])
        node_scores[node] = node_scores.get(node, 0.0) + score

    return node_scores, gen_scores


def gamma_capacity_congestion_score(
    nodes: dict[str, dict[str, float]],
    generators: dict[str, dict[str, float | str]],
    lines: dict[str, dict[str, float | tuple[str, str]]],
    baseline_result: dict[str, dict[str, float]],
) -> dict[str, float]:
    r"""
    Compute gamma-capacity-congestion score (GCCS) per node.

    This score adds two components at each node:

    - a generator-scarcity term based on ``gamma_g P_g^{max}``
    - a congestion term based on the dual values of incident line limits

    Score definition:

    .. math::
       S_v = \sum_{g \in G(v)} \gamma_g P_g^{\max} + \sum_{(v,w) \in \delta(v)} F_{vw}^{\max}\left(\mu_{vw}^{+} + \mu_{vw}^{-}\right)

    Parameters
    ----------
    nodes : dict
        Node data keyed by node label.
    generators : dict
        Generator data keyed by generator id.
    lines : dict
        Line data keyed by line id. Each line must provide ``ends`` and
        ``capacity``.
    baseline_result : dict
        Baseline dispatch outputs containing ``gamma``, ``mu_plus``, and
        ``mu_minus``.

    Returns
    -------
    dict[str, float]
        Node-level gamma-capacity-congestion scores.
    """
    gamma = baseline_result["gamma"]
    mu_plus = baseline_result["mu_plus"]
    mu_minus = baseline_result["mu_minus"]

    node_scores: dict[str, float] = {str(v): 0.0 for v in nodes}

    # Generator term
    for g, data in generators.items():
        node = str(data["node"])
        node_scores[node] = node_scores.get(node, 0.0) + float(gamma[g]) * float(data["p_max"])

    # Line congestion term (added to both incident nodes)
    for l, data in lines.items():
        u, v = data["ends"]
        u = str(u)
        v = str(v)
        term = float(data["capacity"]) * (float(mu_plus[l]) + float(mu_minus[l]))
        node_scores[u] = node_scores.get(u, 0.0) + term
        node_scores[v] = node_scores.get(v, 0.0) + term

    return node_scores


def load_weighted_lmp_score(
    nodes: dict[str, dict[str, float]],
    baseline_result: dict[str, dict[str, float]],
    VOLL: float = 500.0,
    cap_lambda: bool = True,
) -> dict[str, float]:
    r"""
    Compute load-weighted LMP scores from baseline nodal prices and load.

    This score highlights nodes where high prices coincide with high load.
    Optionally, nodal prices can be capped at ``VOLL`` before weighting.

    Score definition:

    .. math::
       S_v = \lambda_v L_v

    When ``cap_lambda`` is enabled, the score becomes:

    .. math::
       S_v = \min(\lambda_v, \mathrm{VOLL}) L_v

    Parameters
    ----------
    nodes : dict
        Node data keyed by node label. Each node must provide ``load``.
    baseline_result : dict
        Baseline dispatch outputs containing ``lambdas``.
    VOLL : float, default=500.0
        Price cap applied when ``cap_lambda`` is enabled.
    cap_lambda : bool, default=True
        Whether to cap nodal prices at ``VOLL`` before scoring.

    Returns
    -------
    dict[str, float]
        Node-level load-weighted LMP scores.
    """
    lambdas = baseline_result["lambdas"]

    node_scores: dict[str, float] = {}
    for v, data in nodes.items():
        node = str(v)
        lam = float(lambdas[node])
        lam_eff = min(lam, VOLL) if cap_lambda else lam
        node_scores[node] = lam_eff * float(data["load"])

    return node_scores


def ptdf_stress_score(
    ptdf: np.ndarray,
    nodes: list[Hashable],
    mask: list[int],
    generators: dict[str, dict[str, float | str]],
    line_margins: np.ndarray | list[float],
    epsilon: float = 1e-6,
) -> dict[Hashable, float]:
    r"""
    Compute PTDF stress score (PTDFS) per node.

    This score combines installed capacity at a node with the node's PTDF
    exposure to lines that have little residual margin. Higher values indicate
    nodes whose injections are both large and strongly coupled to tight lines.

    For each non-slack node :math:`v`:

    .. math::
       S_v = \left(\sum_{g \in G(v)} P_g^{\max}\right)\sum_{\ell}\frac{\left|\mathrm{PTDF}_{\ell,v}\right|}{m_{\ell} + \varepsilon}

    where :math:`m_{\ell}` is the residual line margin and
    :math:`\varepsilon` avoids division by zero.
    Slack node score is set to 0 because PTDF is provided only for non-slack
    columns (given by `mask`).

    Parameters
    ----------
    ptdf : np.ndarray
        PTDF matrix with rows as lines and columns as non-slack buses.
    nodes : list[hashable]
        Node labels in the full network order.
    mask : list[int]
        Indices of non-slack buses corresponding to PTDF columns.
    generators : dict
        Generator data keyed by generator id. Each generator must provide
        ``node`` and ``p_max``.
    line_margins : np.ndarray or list[float]
        Residual margin for each PTDF row / line.
    epsilon : float, default=1e-6
        Small positive stabilizer in the denominator.

    Returns
    -------
    dict[hashable, float]
        PTDF stress score for each node in the full node set.
    """
    margins = np.asarray(line_margins, dtype=float).reshape(-1)
    if margins.shape[0] != ptdf.shape[0]:
        raise ValueError(
            "line_margins length must match PTDF row count. "
            f"Got {margins.shape[0]} and {ptdf.shape[0]}."
        )
    if epsilon <= 0:
        raise ValueError(f"epsilon must be positive; got {epsilon}.")

    capacity_by_node: dict[str, float] = {}
    for data in generators.values():
        node = str(data["node"])
        capacity_by_node[node] = capacity_by_node.get(node, 0.0) + float(data["p_max"])

    stress_non_slack = np.sum(np.abs(ptdf) / (margins[:, None] + float(epsilon)), axis=0)

    scores = {node: 0.0 for node in nodes}
    for col, bus_idx in enumerate(mask):
        node = nodes[bus_idx]
        installed_capacity = capacity_by_node.get(str(node), 0.0)
        scores[node] = installed_capacity * float(stress_non_slack[col])
    return scores
