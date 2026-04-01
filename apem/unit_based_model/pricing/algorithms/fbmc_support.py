import gurobipy as gp


def get_fbmc_pricing_data(allocation):
    return getattr(allocation.TransmissionNetworkAllocation, "fbmc_data", None)


def add_fbmc_price_coupling_constraints(model, p_vt, r_t, gamma_lt, nodes, periods, fbmc_data):
    constraint_ids = fbmc_data["constraint_ids"]
    ptdf = fbmc_data["ptdf"]
    model.addConstrs(
        p_vt[v, t] == r_t[t] - gp.quicksum(ptdf[(line_id, v)] * gamma_lt[line_id, t] for line_id in constraint_ids)
        for v in nodes
        for t in periods
    )


def add_fbmc_gamma_composition_constraints(model, gamma_lt, epsilon_up_lt, epsilon_down_lt, periods, fbmc_data):
    constraint_ids = fbmc_data["constraint_ids"]
    model.addConstrs(
        -gamma_lt[line_id, t] + epsilon_up_lt[line_id, t] + epsilon_down_lt[line_id, t] == 0
        for line_id in constraint_ids
        for t in periods
    )
