import time
from typing import Optional, Union

import gurobipy as gp
from gurobipy import GRB

from apem.unit_based_model.allocation.allocation import Allocation
from apem.unit_based_model.solver_configuration import SolverConfiguration
from apem.unit_based_model.error import Error
from apem.unit_based_model.data.parsing.scenario import Scenario
from apem.unit_based_model.pricing.algorithms.fbmc_support import (
    add_fbmc_gamma_composition_constraints,
    add_fbmc_price_coupling_constraints,
    get_fbmc_pricing_data,
)
from apem.unit_based_model.pricing.algorithms.pricing_algorithm import PricingAlgorithm
from apem.unit_based_model.pricing.analysis.pricing import GLOCS, Pricing
from apem.unit_based_model.pricing.analysis.write_prices import write_prices, write_prices_failure
from apem.unit_based_model.utils.extraction import preprocess_as_dict


class ELMP(PricingAlgorithm):
    """
    Implementation of Extended Locational Marginal Pricing.
    """

    def compute_prices(self, allocation: Allocation, scenario: Scenario, configuration: SolverConfiguration,
                       file_prices: Optional[str] = None,
                       fixed_prices: Optional[Pricing] = None) -> Union[Pricing, Error]:
        """
        Formulates and solves an ELMP problem similar to the one from
        "Pricing Optimal Outcomes in Coupled and Non-Convex Markets: Theory and Applications to Electricity
        Markets" (Appendix C, https://arxiv.org/abs/2209.07386). The method can also be used to compute the
        GLOCs for an allocation-prices pair.

        :param allocation: allocation for which supporting prices are computed
        :param scenario: scenario for which prices are computed
        :param configuration: configuration object containing the parameters for the pricing algorithm
        :param file_prices: name of the file in which results are written
        :param fixed_prices: prices for which GLOCs should be computed
        :return: Pricing object if prices could be computed or Error object otherwise
        """
        if allocation.status != 1:
            if file_prices:
                write_prices_failure(file_prices, str(self), -1)

            print(f'{self} pricing error with code -1')
            return Error(-1)  # Allocation computation failed

        start = time.time()

        model = gp.Model('ELMP-Pricing')

        # apply Gurobi configuration parameters
        configuration.apply_to_model(model)

        df_buyers = scenario.df_buyers
        df_sellers = scenario.df_sellers
        network = scenario.network
        periods = scenario.periods
        blocks_buyers = scenario.blocks_buyers
        blocks_sellers = scenario.blocks_sellers
        r_star = scenario.r_star

        nodes = network.nodes
        buyers = df_buyers['buyer'].unique().tolist()
        sellers = df_sellers['seller'].unique().tolist()
        
        # precompute dictionaries for fast access
        buyer_val_dict, buyer_size_dict = {}, {}
        seller_cost_dict, seller_size_dict = {}, {}
        
        buyer_inelastic_dem_dict = preprocess_as_dict(df_buyers, ['buyer', 'period'], 'inelastic_dem')
        buyer_max_dem_dict = preprocess_as_dict(df_buyers, ['buyer', 'period'], 'max_dem')
        buyer_node_dict = preprocess_as_dict(df_buyers, ['buyer', 'period'], 'node')
        seller_no_load_cost_dict = preprocess_as_dict(df_sellers, ['seller', 'period'], 'no_load_cost')
        seller_min_prod_dict = preprocess_as_dict(df_sellers, ['seller', 'period'], 'min_prod')
        seller_max_prod_dict = preprocess_as_dict(df_sellers, ['seller', 'period'], 'max_prod')
        seller_min_uptime_dict = preprocess_as_dict(df_sellers, ['seller', 'period'], 'min_uptime')
        seller_node_dict = preprocess_as_dict(df_sellers, ['seller', 'period'], 'node')
        
        for block in blocks_buyers:
            buyer_val_dict[block] = preprocess_as_dict(df_buyers, ['buyer', 'period'], 'val', block)
            buyer_size_dict[block] = preprocess_as_dict(df_buyers, ['buyer', 'period'], 'size', block)
            
        for block in blocks_sellers:
            seller_cost_dict[block] = preprocess_as_dict(df_sellers, ['seller', 'period'], 'cost', block)
            seller_size_dict[block] = preprocess_as_dict(df_sellers, ['seller', 'period'], 'size', block)    

        x_bt = allocation.BuyersAllocation.x_bt
        y_st = allocation.SellersAllocation.y_st
        x_btl = allocation.BuyersAllocation.x_btl
        y_stl = allocation.SellersAllocation.y_stl
        f_vwt = allocation.TransmissionNetworkAllocation.f_vwt
        f_vwkt = getattr(allocation.TransmissionNetworkAllocation, "f_vwkt", None)
        u_st = allocation.SellersAllocation.u_st
        fbmc_data = get_fbmc_pricing_data(allocation)
        use_fbmc_network = fbmc_data is not None

        epsilon_up_btl = model.addVars(buyers, periods, blocks_buyers, ub=GRB.INFINITY,
                                       name='epsilon_up_b_t_l')
        epsilon_down_btl = model.addVars(buyers, periods, blocks_buyers, lb=-GRB.INFINITY, ub=0,
                                         name='epsilon_down_b_t_l')
        epsilon_bt = model.addVars(buyers, periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='epsilon_b_t_l')
        epsilon_up_bt = model.addVars(buyers, periods, ub=GRB.INFINITY, name='epsilon_up_b_t')

        epsilon_up_stl = model.addVars(sellers, periods, blocks_sellers, ub=GRB.INFINITY,
                                       name='epsilon_up_s_t_l')
        epsilon_down_stl = model.addVars(sellers, periods, blocks_sellers, lb=-GRB.INFINITY, ub=0,
                                         name='epsilon_down_s_t_l')
        epsilon_st = model.addVars(sellers, periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='epsilon_s_t')
        epsilon_down_st = model.addVars(sellers, periods, lb=-GRB.INFINITY, ub=0, name='epsilon_down_s_t')
        epsilon_up_st = model.addVars(sellers, periods, ub=GRB.INFINITY, name='epsilon_up_s_t')

        p_vt = model.addVars(nodes, periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='p_vt')
        if use_fbmc_network:
            fb_constraint_ids = fbmc_data["constraint_ids"]
            flow_lt = fbmc_data["flow"]
            capacity_upper_lt = fbmc_data["capacity_upper"]
            capacity_lower_lt = fbmc_data["capacity_lower"]
            gamma_lt = model.addVars(fb_constraint_ids, periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='gamma_l_t')
        else:
            is_multigraph = network.is_multigraph()
            if is_multigraph:
                undirected_edges = list(network.edges(keys=True, data=True))  # (u,v,k,data)
            else:
                undirected_edges = [(u, v, None, data) for u, v, data in network.edges(data=True)]

            if is_multigraph:
                if not f_vwkt:
                    if file_prices:
                        write_prices_failure(file_prices, str(self), -2)
                    print(f'{self} pricing error with code -2: missing multigraph per-edge flows')
                    return Error(-2)
                missing_flow_key = next(
                    (
                        (u, v, k, t)
                        for (u, v, k, _) in undirected_edges
                        for t in periods
                        if (u, v, k, t) not in f_vwkt
                    ),
                    None,
                )
                if missing_flow_key is not None:
                    if file_prices:
                        write_prices_failure(file_prices, str(self), -2)
                    print(f'{self} pricing error with code -2: missing multigraph flow key {missing_flow_key}')
                    return Error(-2)

            directed_edges = []
            for idx, (u, v, k, data) in enumerate(undirected_edges):
                directed_edges.append((idx, u, v, k, data))
                directed_edges.append((idx, v, u, k, data))

            flow_et = {}
            for idx, (u, v, k, data) in enumerate(undirected_edges):
                for t in periods:
                    if is_multigraph:
                        base = f_vwkt[(u, v, k, t)]
                    else:
                        base = f_vwt[(u, v, t)]
                    flow_et[(idx, u, v, t)] = base
                    flow_et[(idx, v, u, t)] = -base

            gamma_et = model.addVars([(e, v, w, t) for (e, v, w, _, _) in directed_edges for t in periods],
                                     lb=-GRB.INFINITY, ub=GRB.INFINITY, name='gamma_e_t')
        if fixed_prices:
            model.addConstrs(p_vt[v, t] == fixed_prices.node_prices[v, t] for v in nodes for t in periods)
        if use_fbmc_network:
            epsilon_down_lt = model.addVars(fb_constraint_ids, periods, lb=-GRB.INFINITY, ub=0, name='epsilon_down_l_t')
            epsilon_up_lt = model.addVars(fb_constraint_ids, periods, ub=GRB.INFINITY, name='epsilon_up_l_t')
        else:
            epsilon_down_et = model.addVars([(e, v, w, t) for (e, v, w, _, _) in directed_edges for t in periods],
                                            lb=-GRB.INFINITY, ub=0, name='epsilon_down_e_t')
            epsilon_up_et = model.addVars([(e, v, w, t) for (e, v, w, _, _) in directed_edges for t in periods],
                                          ub=GRB.INFINITY, name='epsilon_up_e_t')

        chi_up_st = model.addVars(sellers, periods, ub=GRB.INFINITY, name='chi_up_s_t')
        chi_down_st = model.addVars(sellers, periods, lb=-GRB.INFINITY, ub=0, name='chi_down_s_t')
        chi_hat_st = model.addVars(sellers, periods, lb=-GRB.INFINITY, ub=0, name='chi_hat_s_t')

        psi_down_st = model.addVars(sellers, periods, lb=-GRB.INFINITY, ub=0, name='psi_down_s_t')
        psi_up_st = model.addVars(sellers, periods, ub=GRB.INFINITY, name='psi_up_s_t')

        r_t = model.addVars(periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='r_t')

        lambda_lb = 0 if use_fbmc_network else -GRB.INFINITY
        lambda_b = model.addVars(buyers, lb=lambda_lb, ub=GRB.INFINITY, name='lambda_b')
        lambda_s = model.addVars(sellers, lb=lambda_lb, ub=GRB.INFINITY, name='lambda_s')
        if use_fbmc_network:
            lambda_lt = model.addVars(fb_constraint_ids, periods, lb=lambda_lb, ub=GRB.INFINITY, name='lambda_l_t')
        else:
            lambda_et = model.addVars([(e, v, w, t) for (e, v, w, _, _) in directed_edges for t in periods],
                                      lb=lambda_lb, ub=GRB.INFINITY, name='lambda_e_t')

        model.update()

        model.setObjective(
            gp.quicksum(lambda_b[b] for b in buyers)
            + gp.quicksum(lambda_s[s] for s in sellers)
            + (
                gp.quicksum(lambda_lt[line_id, t] for line_id in fb_constraint_ids for t in periods)
                if use_fbmc_network
                else gp.quicksum(lambda_et[e, v, w, t] for (e, v, w, _, _) in directed_edges for t in periods)
            ),
            GRB.MINIMIZE
        )
        # 1
        model.addConstrs(
            lambda_b[b]
            - gp.quicksum(
                epsilon_bt[b, t] * buyer_inelastic_dem_dict[b, t]
                + epsilon_up_bt[b, t] * buyer_max_dem_dict[b, t]
                + gp.quicksum(
                    epsilon_up_btl[b, t, lb] * buyer_size_dict[lb][b, t]
                    for lb in blocks_buyers
                )
                for t in periods
            )
            + gp.quicksum(
                buyer_val_dict[lb][b, t] * x_btl[b, t, lb]
                for t in periods
                for lb in blocks_buyers
            )
            - gp.quicksum(
                p_vt[buyer_node_dict[b, t], t] * x_bt[b, t]
                for t in periods
            )
            >= 0
            for b in buyers
        )
        # 2
        model.addConstrs(
            lambda_s[s]
            - gp.quicksum(
                psi_up_st[s, t]
                + gp.quicksum(
                    epsilon_up_stl[s, t, ls] * seller_size_dict[ls][s, t]
                    for ls in blocks_sellers
                )
                for t in periods
            )
            + gp.quicksum(
                p_vt[seller_node_dict[s, t], t] * y_st[s, t]
                for t in periods
            )
            - gp.quicksum(
                seller_cost_dict[ls][s, t] * y_stl[s, t, ls]
                for t in periods
                for ls in blocks_sellers
            )
            - gp.quicksum(
                seller_no_load_cost_dict[s, t] * u_st[s, t]
                for t in periods
            )
            >= 0
            for s in sellers
        )
        # Additional buyer/seller profit-floor constraints (also used in Join pricing).
        # These tighten the dual formulation and prevent unbounded rays in some FBMC cases.
        model.addConstrs(
            gp.quicksum(
                buyer_val_dict[lb][b, t] * x_btl[b, t, lb]
                for t in periods
                for lb in blocks_buyers
            )
            - gp.quicksum(
                p_vt[buyer_node_dict[b, t], t] * x_btl[b, t, lb]
                for t in periods
                for lb in blocks_buyers
            )
            + lambda_b[b]
            >= 0
            for b in buyers
        )
        model.addConstrs(
            gp.quicksum(
                p_vt[seller_node_dict[s, t], t] * y_st[s, t]
                for t in periods
            )
            - gp.quicksum(
                seller_cost_dict[ls][s, t] * y_stl[s, t, ls]
                for t in periods
                for ls in blocks_sellers
            )
            - gp.quicksum(
                seller_no_load_cost_dict[s, t] * u_st[s, t]
                for t in periods
            )
            + lambda_s[s]
            >= 0
            for s in sellers
        )
        if use_fbmc_network:
            for line_id in fb_constraint_ids:
                for t in periods:
                    model.addConstr(
                        lambda_lt[line_id, t]
                        - epsilon_up_lt[line_id, t] * capacity_upper_lt[(line_id, t)]
                        - epsilon_down_lt[line_id, t] * capacity_lower_lt[(line_id, t)]
                        + gamma_lt[line_id, t] * flow_lt[(line_id, t)]
                        >= 0
                    )
            add_fbmc_price_coupling_constraints(model, p_vt, r_t, gamma_lt, nodes, periods, fbmc_data)
            add_fbmc_gamma_composition_constraints(model, gamma_lt, epsilon_up_lt, epsilon_down_lt, periods, fbmc_data)
        else:
            for (e, v, w, k, data) in directed_edges:
                for t in periods:
                    model.addConstr(
                        lambda_et[e, v, w, t]
                        - epsilon_up_et[e, v, w, t] * data['F_max']
                        - epsilon_down_et[e, v, w, t] * (-data['F_max'])
                        + gamma_et[e, v, w, t] * flow_et[(e, v, w, t)]
                        >= 0
                    )
            for v in nodes:
                if v == r_star:
                    continue
                for t in periods:
                    inflow = gp.quicksum(
                        data['B'] * (p_vt[w, t] + gamma_et[e, w, v, t])
                        for (e, w, v2, k, data) in directed_edges
                        if v2 == v
                    )
                    outflow = gp.quicksum(
                        data['B'] * (p_vt[v, t] + gamma_et[e, v, w, t])
                        for (e, v2, w, k, data) in directed_edges
                        if v2 == v
                    )
                    model.addConstr(inflow - outflow == 0)
            for t in periods:
                inflow = gp.quicksum(
                    data['B'] * (p_vt[w, t] + gamma_et[e, w, r_star, t])
                    for (e, w, v2, k, data) in directed_edges
                    if v2 == r_star
                )
                outflow = gp.quicksum(
                    data['B'] * (p_vt[r_star, t] + gamma_et[e, r_star, w, t])
                    for (e, v2, w, k, data) in directed_edges
                    if v2 == r_star
                )
                model.addConstr(r_t[t] + inflow - outflow == 0)
            for (e, v, w, k, data) in directed_edges:
                for t in periods:
                    model.addConstr(
                        -gamma_et[e, v, w, t] + epsilon_up_et[e, v, w, t] + epsilon_down_et[e, v, w, t] == 0
                    )
        # 7
        model.addConstrs(
            epsilon_up_btl[b, t, lb] + epsilon_down_btl[b, t, lb] - epsilon_bt[b, t]
            == buyer_val_dict[lb][b, t]
            for b in buyers
            for t in periods
            for lb in blocks_buyers
        )
        # 8
        model.addConstrs(
            epsilon_bt[b, t] + epsilon_up_bt[b, t] + p_vt[buyer_node_dict[b, t], t]
            == 0
            for b in buyers
            for t in periods
        )
        # 9
        model.addConstrs(
            epsilon_up_stl[s, t, ls] + epsilon_down_stl[s, t, ls] - epsilon_st[s, t]
            == -seller_cost_dict[ls][s, t]
            for s in sellers
            for t in periods
            for ls in blocks_sellers
        )
        # 10
        model.addConstrs(
            epsilon_st[s, t] + epsilon_down_st[s, t] + epsilon_up_st[s, t]
            - p_vt[seller_node_dict[s, t], t]
            == 0
            for s in sellers
            for t in periods
        )
        # 11 if there is more than 1 period
        model.addConstrs(
            -gp.quicksum(
                seller_size_dict[ls][s, 1] * epsilon_up_stl[s, 1, ls]
                for ls in blocks_sellers
            )
            + psi_up_st[s, 1]
            + psi_down_st[s, 1]
            - seller_max_prod_dict[s, 1] * epsilon_up_st[s, 1]
            - seller_min_prod_dict[s, 1] * epsilon_down_st[s, 1]
            + chi_down_st[s, 2]
            == -seller_no_load_cost_dict[s, 1]
            for s in sellers if len(periods) > 1
        )
        # 11 if there is only one period
        model.addConstrs(
            -gp.quicksum(
                seller_size_dict[ls][s, 1] * epsilon_up_stl[s, 1, ls]
                for ls in blocks_sellers
            )
            + psi_up_st[s, 1]
            + psi_down_st[s, 1]
            - seller_max_prod_dict[s, 1] * epsilon_up_st[s, 1]
            - seller_min_prod_dict[s, 1] * epsilon_down_st[s, 1]
            == -seller_no_load_cost_dict[s, 1]
            for s in sellers if len(periods) == 1
        )
        # 12
        model.addConstrs(
            -gp.quicksum(
                seller_size_dict[ls][s, t] * epsilon_up_stl[s, t, ls]
                for ls in blocks_sellers
            )
            + psi_up_st[s, t]
            + psi_down_st[s, t]
            - seller_max_prod_dict[s, t] * epsilon_up_st[s, t]
            - seller_min_prod_dict[s, t] * epsilon_down_st[s, t]
            - chi_up_st[s, t]
            - chi_down_st[s, t]
            + chi_down_st[s, t + 1]
            == -seller_no_load_cost_dict[s, t]
            for s in sellers
            for t in periods if 1 < t < periods[-1]
        )
        # 13 if there is more than 1 period
        model.addConstrs(
            -gp.quicksum(
                seller_size_dict[ls][s, periods[-1]] * epsilon_up_stl[s, periods[-1], ls]
                for ls in blocks_sellers
            )
            + psi_up_st[s, periods[-1]]
            + psi_down_st[s, periods[-1]]
            - seller_max_prod_dict[s, periods[-1]] * epsilon_up_st[s, periods[-1]]
            - seller_min_prod_dict[s, periods[-1]] * epsilon_down_st[s, periods[-1]]
            - chi_up_st[s, periods[-1]]
            - chi_down_st[s, periods[-1]]
            == -seller_no_load_cost_dict[s, periods[-1]]
            for s in sellers if len(periods) > 1
        )
        # 14
        model.addConstrs(
            chi_hat_st[s, t]
            + chi_down_st[s, t]
            + gp.quicksum(
                chi_up_st[s, i]
                for i in range(t, min(periods[-1], t + seller_min_uptime_dict[s, t] - 1) + 1)
            )
            == 0
            for s in sellers for t in periods if t > 1
        )

        model.optimize()

        end = time.time()
        runtime = end - start
        num_vars = model.NumVars
        num_constrs = model.NumConstrs
        status = model.getAttr('Status')

        if status == GRB.OPTIMAL:
            total_glocs = round(model.getObjective().getValue(), 2)
            glocs_buyers = round(sum(lambda_b[b].X for b in buyers), 2)
            glocs_sellers = round(sum(lambda_s[s].X for s in sellers), 2)
            if use_fbmc_network:
                glocs_network = round(sum(lambda_lt[line_id, t].X for line_id in fb_constraint_ids for t in periods), 2)
            else:
                glocs_network = round(
                    sum(lambda_et[e, v, w, t].X for (e, v, w, _, _) in directed_edges for t in periods), 2)
            glocs_per_buyer = {b: round(lambda_b[b].X, 2) for b in buyers}
            glocs_per_seller = {s: round(lambda_s[s].X, 2) for s in sellers}
            if use_fbmc_network:
                glocs_per_line = {
                    line_id: round(sum(lambda_lt[line_id, t].X for t in periods), 2)
                    for line_id in fb_constraint_ids
                }
            else:
                glocs_per_line = {}
                for (e, v, w, _, _) in directed_edges:
                    glocs_per_line[(v, w, e)] = round(sum(lambda_et[e, v, w, t].X for t in periods), 2)

            p_vt = {(v, t): p_vt[v, t].X for v in nodes for t in periods}
            if use_fbmc_network:
                gamma_vwt = {(line_id, t): gamma_lt[line_id, t].X for line_id in fb_constraint_ids for t in periods}
                gamma_vwkt = {}
            else:
                gamma_vwt = {}
                gamma_vwkt = {}
                for (e, v, w, k, _) in directed_edges:
                    for t in periods:
                        gamma_val = gamma_et[e, v, w, t].X
                        gamma_vwt[(v, w, t)] = gamma_vwt.get((v, w, t), 0) + gamma_val
                        gamma_vwkt[(v, w, k, t)] = gamma_val

            pricing = Pricing(p_vt, gamma_vwt, str(self), runtime, num_vars, num_constrs,
                              glocs=GLOCS(total_glocs, glocs_buyers, glocs_sellers, glocs_network,
                                          glocs_per_buyer, glocs_per_seller, glocs_per_line),
                              line_congestion_prices_per_edge=gamma_vwkt)

            if file_prices:
                write_prices(file_prices, pricing, scenario)

            return pricing

        if file_prices:
            write_prices_failure(file_prices, str(self), status)

        print(f'{self} pricing error with code {status}')

        return Error(status)

    def __str__(self):
        return 'ELMP'
