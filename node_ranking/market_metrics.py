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
    """
    Compute rent-weighted dispatch scores from a baseline dispatch.

    Generator score is `max(0, lambda_node - cost_g) * dispatch_g`.
    Node score is the sum of generator scores connected to that node.

    Returns `(node_scores, gen_scores)`.
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
    """
    Compute node dispatch-volume scores from a baseline dispatch.

    Node score is `sum(dispatch_g)` over generators located at the node.
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
    """
    Compute gamma-capacity scores from a baseline dispatch.

    Generator score is `gamma_g * p_max_g`.
    Node score is the sum of generator scores connected to that node.

    Returns `(node_scores, gen_scores)`.
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
    """
    Compute gamma-capacity-congestion score (GCCS) per node.

    Score definition:
      kappa_v = sum_{g in G(v)} gamma_g * Pmax_g
              + sum_{(v,w) in delta(v)} Fmax_vw * (mu_plus_vw + mu_minus_vw)

    Returns node-level scores.
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
    """
    Compute load-weighted LMP scores from baseline nodal prices and load.

    Node score is `lambda_v * load_v` or `min(lambda_v, VOLL) * load_v`
    when `cap_lambda` is enabled.
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
    """
    Compute PTDF stress score (PTDFS) per node.

    For each non-slack node v:
      kappa_v = (sum_{g in G(v)} Pmax_g) * sum_l |PTDF_{l,v}| / (m_l + epsilon)

    where m_l is the residual line margin and epsilon avoids division by zero.
    Slack node score is set to 0 because PTDF is provided only for non-slack
    columns (given by `mask`).
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
