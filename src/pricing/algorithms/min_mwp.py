import time
import gurobipy as gp
from gurobipy import GRB

from src.allocation.allocation import Allocation
from src.allocation.error import Error
from src.data.parsing.scenario import Scenario
from src.utils.extraction import *
from src.pricing.analysis.pricing import Pricing, MWPS
from src.pricing.algorithms.pricing_algorithm import PricingAlgorithm
from src.pricing.analysis.write_prices import write_prices_failure, write_prices


class MinMWP(PricingAlgorithm):
    """Implementation of Minimum Make-Whole Payments Pricing.
    """

    def compute_prices(self, allocation: Allocation, scenario: Scenario, file_prices=None, fixed_prices=None):
        """
        Formulates and solves a Min-MWP problem similar to the one from https://arxiv.org/pdf/2209.07386.pdf
        (Appendix E). The method can also be used to compute the MWPs for an allocation-prices pair.

        :param allocation: allocation for which supporting prices are computed
        :param scenario: scenario for which prices are computed
        :param file_prices: name of the file in which results are written
        :param fixed_prices: prices for which MWPs should be computed
        :return: Pricing object if prices could be computed or Error object otherwise
        """
        if allocation.status != 1:
            if file_prices is not None:
                write_prices_failure(file_prices, str(self), -1)

            print(f'{self} pricing error with code -1')
            return Error(-1)  # Allocation computation failed

        start = time.time()

        model = gp.Model('Min-MWP-Pricing')

        model.setParam("OutputFlag", 0)
        model.setParam('TimeLimit', 60 * 60)

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

        y_st = allocation.SellersAllocation.y_st
        x_btl = allocation.BuyersAllocation.x_btl
        y_stl = allocation.SellersAllocation.y_stl
        f_vwt = allocation.TransmissionNetworkAllocation.f_vwt
        u_st = allocation.SellersAllocation.u_st

        p_vt = model.addVars(nodes, periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='p_vt')
        gamma_vwt = model.addVars([(v, w, t) for v in nodes for w in list(network.neighbors(v))
                                   for t in periods],
                                  lb=-GRB.INFINITY, ub=GRB.INFINITY, name='gamma_v_w_t')
        if fixed_prices:
            model.addConstrs(p_vt[v, t] == fixed_prices.node_prices[v, t] for v in nodes for t in periods)

        r_t = model.addVars(periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='r_t')

        lambda_b = model.addVars(buyers, ub=GRB.INFINITY, name='lambda_b')
        lambda_s = model.addVars(sellers, ub=GRB.INFINITY, name='lambda_s')
        lambda_v_w_t = model.addVars([(v, w, t) for v in nodes for w in list(network.neighbors(v))
                                      for t in periods],
                                     ub=GRB.INFINITY, name='lambda_v_w_t')

        model.update()

        model.setObjective(
            gp.quicksum(lambda_b[b] for b in buyers) +
            gp.quicksum(lambda_s[s] for s in sellers) +
            gp.quicksum(lambda_v_w_t[v, w, t] for v in nodes for w in list(network.neighbors(v)) for t in periods),
            GRB.MINIMIZE
        )
        # 1
        model.addConstrs(
            - gp.quicksum(
                extract_from_buyers(df_buyers, 'val', b, t, lb) * x_btl[b, t, lb]
                for t in periods
                for lb in blocks_buyers
            )
            + gp.quicksum(
                p_vt[extract_from_buyers(df_buyers, 'node', b, t), t] * x_btl[b, t, lb]
                for t in periods
                for lb in blocks_buyers
            )
            - lambda_b[b]
            <= 0
            for b in buyers
        )
        # 2
        model.addConstrs(
            -gp.quicksum(
                p_vt[extract_from_sellers(df_sellers, 'node', s, t), t] * y_st[s, t]
                for t in periods
            )
            + gp.quicksum(
                extract_from_sellers(df_sellers, 'cost', s, t, ls) * y_stl[s, t, ls]
                for t in periods
                for ls in blocks_sellers
            )
            + gp.quicksum(
                extract_from_sellers(df_sellers, 'no_load_cost', s, t) * u_st[s, t]
                for t in periods
            )
            - lambda_s[s]
            <= 0
            for s in sellers
        )
        # 3
        model.addConstrs(
            -gamma_vwt[v, w, t] * f_vwt[v, w, t] - lambda_v_w_t[v, w, t]
            <= 0
            for v in nodes
            for w in list(network.neighbors(v))
            for t in periods
        )
        # 4
        model.addConstrs(
            gp.quicksum(
                network[w][v]['B'] * (p_vt[w, t] + gamma_vwt[w, v, t])
                for w in nodes if v in list(network.neighbors(w))
            )
            - gp.quicksum(
                network[v][w]['B'] * (p_vt[v, t] + gamma_vwt[v, w, t])
                for w in list(network.neighbors(v))
            )
            == 0
            for v in nodes if v != r_star
            for t in periods
        )
        # 5
        model.addConstrs(
            r_t[t]
            + gp.quicksum(
                network[w][r_star]['B'] * (p_vt[w, t] + gamma_vwt[w, r_star, t])
                for w in nodes if r_star in list(network.neighbors(w))
            )
            - gp.quicksum(
                network[r_star][w]['B'] * (p_vt[r_star, t] + gamma_vwt[r_star, w, t])
                for w in list(network.neighbors(r_star))
            )
            == 0
            for t in periods
        )

        model.optimize()

        end = time.time()
        runtime = end - start
        num_vars = model.NumVars
        num_constrs = model.NumConstrs

        status = model.getAttr('Status')

        if status == 2:  # OPTIMAL
            total_mwps = round(model.getObjective().getValue(), 2)
            mwps_buyers = round(sum(lambda_b[b].X for b in buyers), 2)
            mwps_sellers = round(sum(lambda_s[s].X for s in sellers), 2)
            mwps_network = round(
                sum(lambda_v_w_t[v, w, t].X for v in nodes for w in network.neighbors(v) for t in periods), 2)
            mwps_per_buyer = {b: round(lambda_b[b].X, 2) for b in buyers}
            mwps_per_seller = {s: round(lambda_s[s].X, 2) for s in sellers}
            mwps_per_line = {(v, w): round(sum(lambda_v_w_t[v, w, t].X for t in periods), 2)
                             for v in nodes for w in list(network.neighbors(v))}

            p_vt = {(v, t): p_vt[v, t].X for v in nodes for t in periods}
            gamma_vwt = {(v, w, t): gamma_vwt[v, w, t].X
                         for v in nodes for w in list(network.neighbors(v)) for t in periods}

            pricing = Pricing(p_vt, gamma_vwt, str(self), runtime, num_vars, num_constrs,
                              mwps=MWPS(total_mwps, mwps_buyers, mwps_sellers, mwps_network,
                                        mwps_per_buyer, mwps_per_seller, mwps_per_line))

            if file_prices is not None:
                write_prices(file_prices, pricing, scenario)

            return pricing

        if file_prices is not None:
            write_prices_failure(file_prices, str(self), status)

        print(f'{self} pricing error with code {status}')

        return Error(status)

    def __str__(self):
        return 'Min_MWP'
