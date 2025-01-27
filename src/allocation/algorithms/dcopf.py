from typing import Optional, Union

import gurobipy as gp
import pandas as pd
from gurobipy import GRB

from src.allocation.allocation import Allocation
from src.allocation.analysis.stats import compute_stats
from src.allocation.configuration import Configuration
from src.allocation.error import Error
from src.allocation.power_flow_model import PowerFlowModel
from src.data.parsing.scenario import Scenario
from src.utils.extraction import extract_from_buyers, extract_from_sellers


class DCOPF(PowerFlowModel):
    """
    Implementation of the Direct Current Optimal Power Flow Model.
    """

    def solve(self, scenario: Scenario, configuration: Configuration, results_file: Optional[str] = None,
              stats_file: Optional[str] = None, u_fixed: Optional[dict] = None) -> Union[Allocation, Error]:
        """
        Formulate and solve a DCOPF problem in Gurobi similar to the one from https://arxiv.org/pdf/2209.07386.pdf
        (Appendix B).

        :param scenario: scenario for which DCOPF is computed
        :param configuration: values of some parameters to be set in the optimizer
        :param results_file: name of the file in which results are written
        :param stats_file: name of the file that contains the statistics
        :param u_fixed: values of the commitment decision variables to be fixed in the problem
        :return: Allocation object if the problem can be solved optimally or an Error object otherwise
        """
        if configuration.relaxation:
            model = gp.Model(f'DCOPF-LP-Scenario-{scenario}')
        else:
            model = gp.Model(f'DCOPF-MILP-Scenario-{scenario}')

        model.setParam("OutputFlag", configuration.output_flag)
        model.setParam('TimeLimit', configuration.time_limit)

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

        model.setObjective(
            gp.quicksum(
                extract_from_buyers(df_buyers, 'val', b, t, lb) * x_btl[b, t, lb]
                for b in buyers
                for t in periods
                for lb in blocks_buyers
            )
            - gp.quicksum(
                extract_from_sellers(df_sellers, 'cost', s, t, ls) * y_stl[s, t, ls]
                for s in sellers
                for t in periods
                for ls in blocks_sellers
            )
            - gp.quicksum(
                extract_from_sellers(df_sellers, 'no_load_cost', s, t) * u_st[s, t]
                for s in sellers
                for t in periods
            ),
            GRB.MAXIMIZE
        )

        # 1
        model.addConstrs(
            x_btl[b, t, lb] >= 0
            for b in buyers
            for t in periods
            for lb in blocks_buyers
        )
        # 2
        model.addConstrs(
            x_btl[b, t, lb] <= extract_from_buyers(df_buyers, 'size', b, t, lb)
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
            == extract_from_buyers(df_buyers, 'inelastic_dem', b, t)
            for b in buyers
            for t in periods
        )
        # 4
        model.addConstrs(
            x_bt[b, t] <= extract_from_buyers(df_buyers, 'max_dem', b, t)
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
            - extract_from_sellers(df_sellers, 'size', s, t, ls) * u_st[s, t]
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
            - extract_from_sellers(df_sellers, 'min_prod', s, t) * u_st[s, t]
            >= 0
            for s in sellers
            for t in periods
        )
        # 9
        model.addConstrs(
            y_st[s, t]
            - extract_from_sellers(df_sellers, 'max_prod', s, t) * u_st[s, t]
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
                for i in range(t - extract_from_sellers(df_sellers, 'min_uptime', s, t) + 1,
                               t + 1)
            )
            - u_st[s, t]
            <= 0
            for s in sellers
            for t in periods if t >= extract_from_sellers(df_sellers, 'min_uptime', s, t) + 1
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

        model.optimize()

        status = model.getAttr('Status')

        if status == GRB.OPTIMAL:
            welfare = model.getObjective().getValue()

            x_bt = {(b, t): x_bt[b, t].X for b in buyers for t in periods}
            x_btl = {(b, t, lb): x_btl[b, t, lb].X for b in buyers for t in periods for lb in blocks_buyers}
            y_st = {(s, t): y_st[s, t].X for s in sellers for t in periods}
            y_stl = {(s, t, ls): y_stl[s, t, ls].X for s in sellers for t in periods for ls in blocks_sellers}
            u_st = {(s, t): u_st[s, t].X for s in sellers for t in periods}
            f_vwt = {(v, w, t): f_vwt[v, w, t].X for v in nodes for w in list(network.neighbors(v)) for t in periods}
            alpha_vt = {(v, t): alpha_vt[v, t].X for v in nodes for t in periods}
            phi_st = {(s, t): phi_st[s, t].X for s in sellers for t in periods}

            if results_file:
                results = []
                for var in model.getVars():
                    results.append({"variable": var.VarName, "value": var.X})

                df = pd.DataFrame(results, columns=["variable", "value"])
                df.to_csv(results_file, index=False)

            allocation = Allocation(welfare, x_bt, y_st, x_btl, y_stl, f_vwt, alpha_vt, u_st, phi_st, self,
                                    model.Runtime, model.NumVars, model.NumConstrs, model.MIPGap,
                                    model.NumVars - model.NumBinVars, model.NumBinVars, scenario)
            if stats_file:
                compute_stats(stats_file, scenario, configuration, allocation, model)

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

    def __str__(self):
        return 'DCOPF'
