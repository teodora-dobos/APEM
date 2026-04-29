"""Helpers for building and solving the baseline DC economic-dispatch model.

These utilities convert APEM unit-based datasets into the simplified input
format used by the node-ranking routines and solve the baseline dispatch model
that feeds several market-based node scores.
"""

import gurobipy as gp
from gurobipy import GRB

from apem.unit_based_model.enums import UnitBased_Datasets


def _build_dispatch_inputs_from_scenario(scenario, period: int | None):
    """
    Build dispatch input dictionaries from a parsed unit-based scenario.

    Parameters
    ----------
    scenario
        Parsed APEM unit-based scenario.
    period : int or None
        If provided, extract inputs for that single period. Otherwise, build a
        period-aggregated representation.

    Returns
    -------
    tuple[dict, dict, dict]
        ``(nodes, gens, lines)`` with normalized string node identifiers.
    """
    df_buyers = scenario.df_buyers.copy()
    df_sellers = scenario.df_sellers.copy()

    if period is not None:
        df_buyers = df_buyers[df_buyers["period"] == period]
        df_sellers = df_sellers[df_sellers["period"] == period]
        if df_buyers.empty:
            raise ValueError(f"No buyer data found for period={period}.")
        if df_sellers.empty:
            raise ValueError(f"No seller data found for period={period}.")

    # Nodes (loads)
    if period is None:
        node_loads = df_buyers.groupby("node", as_index=True)["max_dem"].mean()
    else:
        node_loads = df_buyers.groupby("node", as_index=True)["max_dem"].sum()
    nodes = {str(node): {"load": float(load)} for node, load in node_loads.items()}

    # Generators
    if period is None:
        grouped = df_sellers.groupby("seller", as_index=False).agg(
            node=("node", "first"),
            p_max=("max_prod", "mean"),
            cost=("cost1", "mean"),
        )
    else:
        grouped = df_sellers.groupby("seller", as_index=False).agg(
            node=("node", "first"),
            p_max=("max_prod", "sum"),
            cost=("cost1", "mean"),
        )

    gens = {
        str(row["seller"]): {
            "node": str(row["node"]),
            "p_max": float(row["p_max"]),
            "cost": float(row["cost"]),
        }
        for _, row in grouped.iterrows()
    }

    # Lines
    lines = {}
    if scenario.network.is_multigraph():
        edge_iter = scenario.network.edges(keys=True, data=True)
        for idx, (u, v, k, data) in enumerate(edge_iter):
            lines[f"l{idx}_{k}"] = {
                "ends": (str(u), str(v)),
                "B": float(data.get("B", 1e-3)),
                "capacity": float(data.get("F_max", 0.0)),
            }
    else:
        edge_iter = scenario.network.edges(data=True)
        for idx, (u, v, data) in enumerate(edge_iter):
            lines[f"l{idx}"] = {
                "ends": (str(u), str(v)),
                "B": float(data.get("B", 1e-3)),
                "capacity": float(data.get("F_max", 0.0)),
            }

    # Ensure all referenced line/generator nodes exist in nodes (0 load fallback)
    for g in gens.values():
        if g["node"] not in nodes:
            nodes[g["node"]] = {"load": 0.0}
    for line in lines.values():
        u, v = line["ends"]
        if u not in nodes:
            nodes[u] = {"load": 0.0}
        if v not in nodes:
            nodes[v] = {"load": 0.0}

    return nodes, gens, lines


def build_dispatch_inputs(
    dataset: UnitBased_Datasets,
    period: int | None = None,
):
    """
    Build dispatch input dictionaries from a unit-based dataset.

    Parameters
    ----------
    dataset : UnitBased_Datasets
        Dataset enum entry to parse.
    period : int or None
        If provided, extract inputs for that single period. Otherwise, build a
        period-aggregated representation.

    Returns
    -------
    tuple[dict, dict, dict]
        ``(nodes, gens, lines)`` for the selected period or period-average.
    """
    scenario = dataset.value.parse_data()
    return _build_dispatch_inputs_from_scenario(scenario, period=period)


def solve_economic_dispatch(
    dataset: UnitBased_Datasets,
    fail_nodes=None,
    period: int | None = None,
    VOLL: float = 500.0,
):
    """
    Solve DC economic dispatch with optional generator-node interdictions.

    Uses a single-period model if `period` is provided, otherwise period-averaged
    inputs.

    Interdiction semantics in this model:

    - A node listed in `fail_nodes` is *not* removed from the network.
    - Transmission lines incident to that node remain available.
    - Demand at that node is still present and must be served or shed.
    - Only generators connected to interdicted nodes are forced unavailable
      (their dispatch upper bound is set to zero).

    In other words, this is a generator-node interdiction (GNI) model, not
    a bus-outage or line-outage model.

    Parameters
    ----------
    dataset : UnitBased_Datasets
        Dataset enum entry to parse and solve.
    fail_nodes : iterable or None, default=None
        Node labels whose generators should be disabled.
    period : int or None, default=None
        If provided, solve a single-period problem. Otherwise, solve on the
        period-aggregated representation built by
        :func:`build_dispatch_inputs`.
    VOLL : float, default=500.0
        Value of lost load used as the load-shedding penalty.

    Returns
    -------
    dict or None
        ``None`` if the optimization is not optimal. Otherwise a dictionary
        containing at least ``cost``, ``shed_total``, ``dispatch``,
        ``lambdas``, ``gamma``, ``shed``, ``flows``, ``mu_plus``, and
        ``mu_minus``.
    """
    fail_nodes = {str(node) for node in (fail_nodes or [])}
    scenario = dataset.value.parse_data()
    nodes, gens, lines = _build_dispatch_inputs_from_scenario(scenario, period=period)

    m = gp.Model("economic_dispatch")
    m.Params.OutputFlag = 0

    y = m.addVars(gens.keys(), lb=0, name="gen")
    shed = m.addVars(nodes.keys(), lb=0, name="shed")
    f = m.addVars(lines.keys(), lb=-GRB.INFINITY, name="flow")
    alpha = m.addVars(nodes.keys(), lb=-GRB.INFINITY, name="angle")

    m.setObjective(
        gp.quicksum(gens[g]["cost"] * y[g] for g in gens) + gp.quicksum(VOLL * shed[v] for v in nodes),
        GRB.MINIMIZE,
    )

    # pick a reference bus (alphabetical order for determinism)
    ref_bus = sorted(nodes)[0]
    m.addConstr(alpha[ref_bus] == 0, name="ref_bus")

    # balance with DC flows
    bal = {}
    for v in nodes:
        gen_sum = gp.quicksum(y[g] for g in gens if gens[g]["node"] == v and (v not in fail_nodes))
        effective_load = nodes[v]["load"]
        flow_out = gp.quicksum(f[l] for l, data in lines.items() if data["ends"][0] == v)
        flow_in = gp.quicksum(f[l] for l, data in lines.items() if data["ends"][1] == v)
        bal[v] = m.addConstr(gen_sum - (effective_load - shed[v]) - (flow_out - flow_in) == 0, name=f"bal_{v}")

    # generator limits (GNI: generators at failed nodes are disabled)
    gen_ub = {}
    for g, data in gens.items():
        fail = 1 if data["node"] in fail_nodes else 0
        gen_ub[g] = m.addConstr(y[g] <= data["p_max"] * (1 - fail), name=f"gen_ub_{g}")

    # lines with DC flow f = B (alpha_u - alpha_v)
    line_ub = {}
    line_lb = {}
    for l, data in lines.items():
        u, v = data["ends"]
        B = data.get("B", 1e-3)
        m.addConstr(f[l] == B * (alpha[u] - alpha[v]), name=f"ohm_{l}")
        line_ub[l] = m.addConstr(f[l] <= data["capacity"], name=f"cap_up_{l}")
        line_lb[l] = m.addConstr(f[l] >= -data["capacity"], name=f"cap_lo_{l}")

    m.optimize()
    if m.status != GRB.OPTIMAL:
        return None

    cost = m.ObjVal
    shed_total = sum(shed[v].X for v in nodes)
    dispatch = {g: y[g].X for g in gens}
    lambdas = {v: bal[v].Pi for v in nodes}
    gamma = {g: -gen_ub[g].Pi for g in gens}
    shed_vals = {v: shed[v].X for v in nodes}
    flows = {l: f[l].X for l in lines}
    mu_plus = {l: line_ub[l].Pi for l in lines}
    mu_minus = {l: -line_lb[l].Pi for l in lines}
    return {
        "cost": cost,
        "shed_total": shed_total,
        "dispatch": dispatch,
        "lambdas": lambdas,
        "gamma": gamma,
        "shed": shed_vals,
        "flows": flows,
        "mu_plus": mu_plus,
        "mu_minus": mu_minus,
    }


def economic_dispatch_cost(
    dataset: UnitBased_Datasets,
    fail_nodes=None,
    period: int | None = None,
    VOLL: float = 500.0,
):
    """
    Compute total dispatch cost and total load shed.

    Parameters
    ----------
    dataset : UnitBased_Datasets
        Dataset enum entry to solve.
    fail_nodes : iterable or None, default=None
        Node labels whose generators should be disabled.
    period : int or None, default=None
        If provided, solve a single-period problem.
    VOLL : float, default=500.0
        Value of lost load used as the load-shedding penalty.

    Returns
    -------
    tuple[float, float] or None
        ``(cost, shed_total)`` if the dispatch problem is solved to optimality,
        otherwise ``None``.
    """
    result = solve_economic_dispatch(dataset, fail_nodes=fail_nodes, period=period, VOLL=VOLL)
    if result is None:
        return None
    return result["cost"], result["shed_total"]
