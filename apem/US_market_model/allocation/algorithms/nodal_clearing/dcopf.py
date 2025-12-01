import csv
import os
from pathlib import Path
from typing import Optional, Union, Any, Dict
import re

import gurobipy as gp
import pandas as pd
from gurobipy import GRB

from apem.US_market_model.allocation.allocation import Allocation, SellersAllocation
from apem.US_market_model.allocation.analysis.stats import compute_stats
from apem.US_market_model.allocation.configuration import Configuration
from apem.US_market_model.allocation.error import Error
from apem.US_market_model.allocation.power_flow_model import PowerFlowModel
from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.utils.extraction import preprocess_as_dict

M = 10 ** 15


class DCOPF(PowerFlowModel):
    """
    Implementation of the Direct Current Optimal Power Flow Model. The class is also used for computing redispatch.
    """

    def solve(self, scenario: Scenario, configuration: Configuration, results_file: Optional[str] = None,
              stats_file: Optional[str] = None, u_fixed: Optional[dict] = None,
              redispatch_type: Optional[str] = None, zonal_allocation: Optional[SellersAllocation] = None,
              redispatch_constraint_units: bool = False, redispatch_threshold: float = 0.001,
              shadow_prices: bool = False, alpha: float = 0) -> Union[Allocation, Error]:
        """
        Formulate and solve a DCOPF problem in Gurobi similar to the one from https://arxiv.org/pdf/2209.07386.pdf
        (Appendix B).

        :param scenario: scenario for which DCOPF is computed
        :param configuration: values of some parameters to be set in the optimizer
        :param results_file: name of the file in which results are written
        :param stats_file: name of the file that contains the statistics
        :param u_fixed: values of the commitment decision variables to be fixed in the problem
        :param redispatch_type: type if redispatch
        :param constrain_units: whether only a subset of units can be used for redispatch
        :param threshold: threshold for deciding what units are redispatchable
        :param zonal_allocation: zonal allocation for which a redispatch solution should be computed
        :param redispatch_constraint_units: True if all units can be used for redispatch, False otherwise
        :param redispatch_threshold: production threshold for filtering what units can be redispatched
        :param shadow_prices: whether shadow prices for the computed allocation should be calculated
        :param alpha: used for markup pricing
        :return: Allocation object if the problem can be solved optimally or an Error object otherwise
        """
        if configuration.relaxation:
            model = gp.Model(f'DCOPF-LP-Scenario-{scenario}')
        else:
            model = gp.Model(f'DCOPF-MILP-Scenario-{scenario}')

        # apply Gurobi configuration parameters
        configuration.apply_to_model(model)

        if not configuration.relaxation:
            model.setParam('IntegralityFocus', 1)

        df_buyers = scenario.df_buyers
        df_sellers = scenario.df_sellers
        network = scenario.network
        periods = scenario.periods
        nodes_agents = scenario.nodes_agents
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
        seller_no_load_cost_dict = preprocess_as_dict(df_sellers, ['seller', 'period'], 'no_load_cost')
        seller_min_prod_dict = preprocess_as_dict(df_sellers, ['seller', 'period'], 'min_prod')
        seller_max_prod_dict = preprocess_as_dict(df_sellers, ['seller', 'period'], 'max_prod')
        seller_min_uptime_dict = preprocess_as_dict(df_sellers, ['seller', 'period'], 'min_uptime')

        for block in blocks_buyers:
            buyer_val_dict[block] = preprocess_as_dict(df_buyers, ['buyer', 'period'], 'val', block)
            buyer_size_dict[block] = preprocess_as_dict(df_buyers, ['buyer', 'period'], 'size', block)

        for block in blocks_sellers:
            seller_cost_dict[block] = preprocess_as_dict(df_sellers, ['seller', 'period'], 'cost', block)
            seller_size_dict[block] = preprocess_as_dict(df_sellers, ['seller', 'period'], 'size', block)

        x_bt = model.addVars(buyers, periods, name='x_bt')
        x_btl = model.addVars(buyers, periods, blocks_buyers, name='x_btl')
        y_st = model.addVars(sellers, periods, name='y_st')
        y_stl = model.addVars(sellers, periods, blocks_sellers, name='y_stl')

        if configuration.relaxation:
            u_st = model.addVars(sellers, periods, lb=0, ub=1, name='u_st')
        else:
            u_st = model.addVars(sellers, periods, vtype=GRB.BINARY, name='u_st')

        if u_fixed:
            model.addConstrs(
                u_st[s, t] == u_fixed[s, t] for s in sellers for t in periods if (s, t) in u_fixed.keys()
            )

        phi_st = model.addVars(sellers, periods, lb=0, ub=GRB.INFINITY, name='phi_st')
        alpha_vt = model.addVars(nodes, periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='alpha_vt')
        f_vwt = model.addVars([(v, w, t) for v in nodes for w in list(network.neighbors(v)) for t in periods],
                              lb=-GRB.INFINITY, ub=GRB.INFINITY, name='f_vwt')
        slack = model.addVars([(v, t) for v in nodes for t in periods], lb=-GRB.INFINITY, ub=GRB.INFINITY,
                              name='slack_vt')
        abs_slack = model.addVars([(v, t) for v in nodes for t in periods], lb=0, ub=GRB.INFINITY,
                                  name='abs_slack_vt')

        if not redispatch_type:
            model.setObjective(
                gp.quicksum(
                    buyer_val_dict[lb][b, t] * x_btl[b, t, lb]
                    for b in buyers
                    for t in periods
                    for lb in blocks_buyers
                )
                - gp.quicksum(
                    seller_cost_dict[ls][s, t] * y_stl[s, t, ls]
                    for s in sellers
                    for t in periods
                    for ls in blocks_sellers
                )
                - gp.quicksum(
                    seller_no_load_cost_dict[s, t] * u_st[s, t]
                    for s in sellers
                    for t in periods
                )
                - M * gp.quicksum(abs_slack[v, t] for v in nodes for t in periods),
                GRB.MAXIMIZE
            )
        else:
            self.add_redispatch_constraints_objective(redispatch_type, model, scenario, y_stl, u_st, abs_slack,
                                                      seller_cost_dict, seller_no_load_cost_dict, zonal_allocation,
                                                      redispatch_constraint_units, redispatch_threshold)

        # 1
        model.addConstrs(
            x_btl[b, t, lb] >= 0
            for b in buyers
            for t in periods
            for lb in blocks_buyers
        )
        # 2
        model.addConstrs(
            x_btl[b, t, lb] <= buyer_size_dict[lb][b, t]
            for b in buyers
            for t in periods
            for lb in blocks_buyers
        )
        # 3
        model.addConstrs(
            x_bt[b, t]
            - gp.quicksum(
                x_btl[b, t, lb]
                for lb in blocks_buyers
            )
            == buyer_inelastic_dem_dict[b, t]
            for b in buyers
            for t in periods
        )
        # 4
        model.addConstrs(
            x_bt[b, t] <= buyer_max_dem_dict[b, t]
            for b in buyers
            for t in periods
        )
        # 5
        model.addConstrs(
            y_stl[s, t, ls] >= 0
            for s in sellers
            for t in periods
            for ls in blocks_sellers
        )
        # 6
        model.addConstrs(
            y_stl[s, t, ls]
            - seller_size_dict[ls][s, t] * u_st[s, t]
            <= 0
            for s in sellers
            for t in periods
            for ls in blocks_sellers
        )
        # 7
        model.addConstrs(
            y_st[s, t]
            - gp.quicksum(
                y_stl[s, t, ls]
                for ls in blocks_sellers
            )
            == 0
            for s in sellers
            for t in periods
        )
        # 8
        model.addConstrs(
            y_st[s, t]
            - seller_min_prod_dict[s, t] * u_st[s, t]
            >= 0
            for s in sellers
            for t in periods
        )
        # 9
        model.addConstrs(
            y_st[s, t]
            - seller_max_prod_dict[s, t] * u_st[s, t]
            <= 0
            for s in sellers
            for t in periods
        )
        # 10
        model.addConstrs(
            phi_st[s, t] - u_st[s, t] + u_st[s, t - 1] >= 0
            for s in sellers
            for t in periods if t > 1
        )
        # 11
        model.addConstrs(
            gp.quicksum(
                phi_st[s, i]
                for i in range(t - seller_min_uptime_dict[s, t] + 1,
                               t + 1)
            )
            - u_st[s, t]
            <= 0
            for s in sellers
            for t in periods if t >= seller_min_uptime_dict[s, t] + 1
        )
        # 12
        model.addConstrs(
            f_vwt[v, w, t] >= -network[v][w]['F_max']
            for v in nodes
            for w in list(network.neighbors(v))
            for t in periods
        )
        # 13
        model.addConstrs(
            f_vwt[v, w, t] <= network[v][w]['F_max']
            for v in nodes
            for w in list(network.neighbors(v))
            for t in periods
        )
        # 14
        model.addConstrs(
            (f_vwt[v, w, t] - network[v][w]['B'] * (alpha_vt[v, t] - alpha_vt[w, t]) == 0
             for v in nodes
             for w in list(network.neighbors(v))
             for t in periods)
        )
        # 15
        model.addConstrs(
            (gp.quicksum(
                y_st[s, t]
                for s in nodes_agents[v]['sellers']
            )
             - gp.quicksum(
                x_bt[b, t]
                for b in nodes_agents[v]['buyers']
            )
             - gp.quicksum(
                f_vwt[v, w, t]
                for w in list(network.neighbors(v))
            )
             + slack[v, t]
             == 0
             for t in periods
             for v in nodes),
            name='supply_demand'
        )
        # 16
        model.addConstrs(
            alpha_vt[r_star, t] == 0
            for t in periods
        )

        # linearize abs_slack = abs(slack)
        for v in nodes:
            for t in periods:
                model.addConstr(abs_slack[v, t] >= slack[v, t])
                model.addConstr(abs_slack[v, t] >= -slack[v, t])

        model.optimize()

        status = model.Status

        if status == GRB.OPTIMAL:
            obj = model.ObjVal

            x_bt = {(b, t): x_bt[b, t].X for b in buyers for t in periods}
            x_btl = {(b, t, lb): x_btl[b, t, lb].X for b in buyers for t in periods for lb in blocks_buyers}
            y_st = {(s, t): y_st[s, t].X for s in sellers for t in periods}
            y_stl = {(s, t, ls): y_stl[s, t, ls].X for s in sellers for t in periods for ls in blocks_sellers}
            u_st = {(s, t): u_st[s, t].X for s in sellers for t in periods}
            f_vwt = {(v, w, t): f_vwt[v, w, t].X for v in nodes for w in list(network.neighbors(v)) for t in periods}
            alpha_vt = {(v, t): alpha_vt[v, t].X for v in nodes for t in periods}
            phi_st = {(s, t): phi_st[s, t].X for s in sellers for t in periods}
            slack_vt = {(v, t): slack[v, t].X for v in nodes for t in periods}
            abs_slack_vt = {(v, t): abs_slack[v, t].X for v in nodes for t in periods}

            if results_file:
                results = []
                for var in model.getVars():
                    results.append({"variable": var.VarName, "value": var.X})

                df = pd.DataFrame(results, columns=["variable", "value"])
                df.to_csv(results_file, index=False)

            allocation = Allocation(welfare=obj, x_bt=x_bt, y_st=y_st, x_btl=x_btl, y_stl=y_stl, f_vwt=f_vwt,
                                    alpha_vt=alpha_vt, u_st=u_st, phi_st=phi_st, slack_vt=slack_vt,
                                    power_flow_model=self, runtime=model.Runtime, num_vars=model.NumVars,
                                    num_constrs=model.NumConstrs, MIP_gap=model.MIPGap if model.IsMIP else 0.0,
                                    num_cont_vars=model.NumVars - model.NumBinVars, num_bin_vars=model.NumBinVars,
                                    dataset=scenario)
            if stats_file:
                if not redispatch_type:
                    compute_stats(stats_file, scenario, configuration, allocation, model)
                    print('-' * 50)
                    print(f"DCOPF Objective: {obj}")
                    print('-' * 50)

                    root, _ = os.path.splitext(results_file)
                    dirpath = os.path.dirname(root)
                    if dirpath:
                        os.makedirs(dirpath, exist_ok=True)

                    seller_prices_file = f"{root}_seller_prices_alpha{alpha}.csv"
                    buyer_prices_file = f"{root}_buyer_prices_alpha{alpha}.csv"

                    if shadow_prices:
                        print("Computing shadow prices...")
                        duals = model.getAttr("Pi", model.getConstrs())
                        rows_seller = []
                        rows_buyer = []

                        for c, pi in zip(model.getConstrs(), duals):
                            if "supply_demand" in c.ConstrName:
                                match = re.search(r"\[(\d+),(\d+)\]", c.ConstrName)
                                if match:
                                    period, node = match.groups()
                                    rows_seller.append([int(node), int(period), round(-pi, 2)])
                                    rows_buyer.append([int(node), int(period), (1 + alpha) * round(-pi, 2)])

                        # Sort by node, then period
                        rows_seller.sort(key=lambda x: (x[0], x[1]))
                        rows_buyer.sort(key=lambda x: (x[0], x[1]))

                        # seller prices
                        with open(seller_prices_file, mode="w", newline="") as f:
                            writer = csv.writer(f)
                            writer.writerow(["node", "period", "price"])
                            writer.writerows(rows_seller)

                        # buyer prices
                        with open(buyer_prices_file, mode="w", newline="") as f:
                            writer = csv.writer(f)
                            writer.writerow(["node", "period", "price"])
                            writer.writerows(rows_buyer)

                else:
                    f = open(stats_file, 'w+')
                    f.write(f'Redispatch objective: {obj}')
                    f.close()

                    alloc_comparison_file = Path(stats_file).with_name(
                        f"{redispatch_type}_{redispatch_constraint_units}_{redispatch_threshold}_zonal_final_alloc_comparison.csv")

                    redispatch_costs_file = Path(stats_file).with_name(
                        f"{redispatch_type}_{redispatch_constraint_units}_{redispatch_threshold}_redispatch_costs.csv")

                    redispatch_vols_file = Path(stats_file).with_name(
                        f"{redispatch_type}_{redispatch_constraint_units}_{redispatch_threshold}_redispatch_vols.csv")

                    self.compare_zonal_vs_final_allocation(zonal_allocation=zonal_allocation,
                                                           final_allocation=allocation.SellersAllocation,
                                                           file=str(alloc_comparison_file))

                    self.compute_redispatch_costs(zonal_allocation=zonal_allocation,
                                                  final_allocation=allocation.SellersAllocation,
                                                  seller_cost_dict=seller_cost_dict,
                                                  periods=periods, blocks_sellers=blocks_sellers, sellers=sellers,
                                                  seller_no_load_cost_dict=seller_no_load_cost_dict,
                                                  file=str(redispatch_costs_file))

                    self.compute_redispatch_volumes(zonal_allocation=zonal_allocation,
                                                    final_allocation=allocation.SellersAllocation,
                                                    periods=periods, blocks_sellers=blocks_sellers, sellers=sellers,
                                                    file=str(redispatch_vols_file))

            if any(x > 1e-5 for x in abs_slack_vt.values()):
                nonzero = {(v, t): val for (v, t), val in slack_vt.items() if abs(val) > 1e-5}
                print('-' * 50)
                print(f'Nonzero slack detected at the following (node, period) pairs: {nonzero}')
                print('-' * 50)

            return allocation

        else:
            if results_file:
                status_message = {
                    GRB.INF_OR_UNBD: "Model is infeasible or unbounded",
                    GRB.INFEASIBLE: "Model is infeasible",
                    GRB.UNBOUNDED: "Model is unbounded",
                    GRB.INTERRUPTED: "Optimization was interrupted",
                }.get(model.Status, "Optimization failed with unknown status")

                error_data = [{"status": model.Status, "message": status_message}]
                df = pd.DataFrame(error_data, columns=["status", "message"])
                df.to_csv(results_file, index=False)

            print(f'{self} allocation error with code {status}')
            error = Error(status)
            return error

    def add_redispatch_constraints_objective(self, redispatch_type: str, model: Any, scenario: Scenario,
                                             y_stl: Dict, u_st: Dict, abs_slack: Any, seller_cost_dict: Dict,
                                             seller_no_load_cost_dict: Dict, zonal_allocation: SellersAllocation,
                                             redispatch_constraint_units: bool = False,
                                             redispatch_threshold: float = 0.001) -> gp.Model:
        """
        Include redispatch constraints and objective in the DCOPF model.

        :param redispatch_type: {"MinAbsCostRD", "MinAbsVolRD", "MinCostRD"}.
            - MinAbsCostRD: minimize absolute cost deviations relative to zonal_allocation
            - MinAbsVolRD: minimize absolute volume deviations relative to zonal_allocation
            - MinCostRD: minimize (signed) redispatch cost relative to zonal_allocation
        :param model: The working optimization model
        :param scenario: Holds df_sellers, periods, and blocks_sellers
        :param y_stl: Decision variables for seller s, period t, block ls
        :param u_st: Commitment (on/off) variables for seller s in period t
        :param abs_slack: Absolute values of the slack variables used in the node balance constraints
        :param seller_cost_dict: Marginal cost per block (by (s, t)) for each ls
        :param seller_no_load_cost_dict: No-load/startup-like (fixed) cost per (s, t)
        :param zonal_allocation: Reference allocation
        :param redispatch_constraint_units: If True and a seller's max_prod < redispatch_threshold, set u_st == zonal_allocation.u_st
        :param redispatch_threshold: Production threshold for filtering which units can be redispatched
        :return: updated model
        """

        df_sellers = scenario.df_sellers
        periods = scenario.periods
        blocks_sellers = scenario.blocks_sellers
        sellers = df_sellers['seller'].unique().tolist()

        if redispatch_type in ['MinAbsCostRD', 'MinAbsVolRD']:
            diff_stl = model.addVars(sellers, periods, blocks_sellers, lb=0, name='diff_y_stl')
            u_diff_st = model.addVars(sellers, periods, lb=0, name=f'diff_u_st')

            model.addConstrs(
                zonal_allocation.y_stl[s, t, ls] - y_stl[s, t, ls] <= diff_stl[s, t, ls]
                for s in sellers for t in periods for ls in blocks_sellers
            )

            model.addConstrs(
                y_stl[s, t, ls] - zonal_allocation.y_stl[s, t, ls] <= diff_stl[s, t, ls]
                for s in sellers for t in periods for ls in blocks_sellers)

            if redispatch_type == 'MinAbsCostRD':
                model.setObjective(
                    gp.quicksum(
                        seller_cost_dict[ls][s, t] * diff_stl[s, t, ls]
                        for s in sellers for t in periods for ls in blocks_sellers
                    ) +
                    gp.quicksum(
                        seller_no_load_cost_dict[s, t] * u_diff_st[s, t]
                        for s in sellers for t in periods)
                    +
                    M * gp.quicksum(abs_slack[v, t] for v in scenario.network.nodes for t in periods),
                    GRB.MINIMIZE
                )

                model.addConstrs(
                    zonal_allocation.u_st[s, t] - u_st[s, t] <= u_diff_st[s, t] for s in sellers for t in periods
                )

                model.addConstrs(
                    u_st[s, t] - zonal_allocation.u_st[s, t] <= u_diff_st[s, t] for s in sellers for t in periods
                )

            elif redispatch_type == 'MinAbsVolRD':
                model.setObjective(
                    gp.quicksum(
                        diff_stl[s, t, ls]
                        for s in sellers for t in periods for ls in blocks_sellers
                    ) +
                    M * gp.quicksum(abs_slack[v, t] for v in scenario.network.nodes for t in periods),
                    GRB.MINIMIZE
                )

        elif redispatch_type == 'MinCostRD':
            if redispatch_constraint_units:
                seller_period_max_prod = {
                    (row.seller, row.period): row.max_prod
                    for row in df_sellers.itertuples(index=False)
                }
                for (s, t) in seller_period_max_prod:
                    if seller_period_max_prod[s, t] < redispatch_threshold:
                        model.addConstr(u_st[s, t] == zonal_allocation.u_st[s, t])

            model.setObjective(
                gp.quicksum(
                    seller_cost_dict[ls][s, t] * (y_stl[s, t, ls] - zonal_allocation.y_stl[s, t, ls])
                    for s in sellers for t in periods for ls in blocks_sellers
                ) +
                gp.quicksum(
                    seller_no_load_cost_dict[s, t] * (u_st[s, t] - zonal_allocation.u_st[s, t])
                    for s in sellers for t in periods)
                +
                M * gp.quicksum(abs_slack[v, t] for v in scenario.network.nodes for t in periods),
                GRB.MINIMIZE
            )

        return model

    def compare_zonal_vs_final_allocation(self, zonal_allocation: SellersAllocation,
                                          final_allocation: SellersAllocation, file: str):
        """
        Create a CSV file comparing the zonal allocation and the final allocation obtained after redispatch.
        """
        rows = []

        # u_st
        for (s, t), v_z in zonal_allocation.u_st.items():
            rows.append({
                "var": "u_st", "seller": s, "period": t, "block": None,
                "zonal": v_z, "final": final_allocation.u_st[(s, t)]
            })

        # y_st
        for (s, t), v_z in zonal_allocation.y_st.items():
            rows.append({
                "var": "y_st", "seller": s, "period": t, "block": None,
                "zonal": v_z, "final": final_allocation.y_st[(s, t)]
            })

        # y_stl
        for (s, t, ls), v_z in zonal_allocation.y_stl.items():
            rows.append({
                "var": "y_stl", "seller": s, "period": t, "block": ls,
                "zonal": v_z, "final": final_allocation.y_stl[(s, t, ls)]
            })

        df = pd.DataFrame(rows)
        df["diff"] = df["final"] - df["zonal"]
        df = df.sort_values(["var", "seller", "period", "block"]).reset_index(drop=True)

        p = Path(file)
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(p, index=False)

    def compute_redispatch_costs(self, zonal_allocation: SellersAllocation, final_allocation: SellersAllocation,
                                 seller_cost_dict, seller_no_load_cost_dict, periods, blocks_sellers, sellers,
                                 file: str):
        """
        Compute the signed redispatch cost relative to the zonal allocation.
        """
        redispatch_costs = sum(
            seller_cost_dict[ls][s, t] * (final_allocation.y_stl[s, t, ls] - zonal_allocation.y_stl[s, t, ls])
            for s in sellers for t in periods for ls in blocks_sellers
        ) + sum(
            seller_no_load_cost_dict[s, t] * (final_allocation.u_st[s, t] - zonal_allocation.u_st[s, t])
            for s in sellers for t in periods)

        print('-' * 50)
        print(f"Redispatch costs: {redispatch_costs}")
        print('-' * 50)

        f = open(file, 'w+')
        f.write(f'Redispatch costs: {redispatch_costs}')
        f.close()

    def compute_redispatch_volumes(self, zonal_allocation: SellersAllocation, final_allocation: SellersAllocation,
                                   periods, blocks_sellers, sellers, file: str):
        """
        Compute the total redispatch volume as the L1 norm of dispatch changes between the zonal solution and
        the post-redispatch solution.
        For each seller s, period t, and seller block l, the redispatch volume is | y_stl(final) − y_stl(zonal) |.
        """
        redispatch_volumes = sum(
            abs(final_allocation.y_stl[s, t, ls] - zonal_allocation.y_stl[s, t, ls])
            for s in sellers for t in periods for ls in blocks_sellers
        )

        print('-' * 50)
        print(f"Redispatch volumes: {redispatch_volumes}")
        print('-' * 50)

        f = open(file, 'w+')
        f.write(f'Redispatch volumes: {redispatch_volumes}')
        f.close()

    def __str__(self):
        return 'DCOPF'
