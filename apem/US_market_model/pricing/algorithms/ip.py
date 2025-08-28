import time
from typing import Optional, Union

import gurobipy as gp
from gurobipy import GRB

from apem.US_market_model.allocation.allocation import Allocation
from apem.US_market_model.allocation.configuration import Configuration
from apem.US_market_model.allocation.error import Error
from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.pricing.algorithms.pricing_algorithm import PricingAlgorithm
from apem.US_market_model.pricing.analysis.pricing import LLOCS, Pricing
from apem.US_market_model.pricing.analysis.write_prices import write_prices, write_prices_failure
from apem.US_market_model.utils.extraction import preprocess_as_dict


class IP(PricingAlgorithm):
    """
    Implementation of Integer Programming Pricing.
    """

    def compute_prices(self, allocation: Allocation, scenario: Scenario, configuration: Configuration, file_prices: Optional[str] = None,
                       fixed_prices: Optional[Pricing] = None) -> Union[Pricing, Error]:
        """
        Formulates and solves an IP problem similar to the one from https://arxiv.org/pdf/2209.07386.pdf
        (Appendix D). The method can also be used to compute the LLOCs for an allocation-prices pair.

        :param allocation: allocation for which supporting prices are computed
        :param scenario: scenario for which prices are computed
        :param configuration: configuration object containing the parameters for the pricing algorithm
        :param file_prices: name of the file in which results are written
        :param fixed_prices: prices for which LLOCs should be computed
        :return: Pricing object if prices could be computed or Error object otherwise
        """
        if allocation.status != 1:
            if file_prices:
                write_prices_failure(file_prices, str(self), -1)

            print(f'{self} pricing error with code -1')
            return Error(-1)  # Allocation computation failed

        start = time.time()

        model = gp.Model('IP-Pricing')
        
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
        u_st = allocation.SellersAllocation.u_st

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
        gamma_vwt = model.addVars([(v, w, t) for v in nodes for w in list(network.neighbors(v))
                                   for t in periods],
                                  lb=-GRB.INFINITY, ub=GRB.INFINITY, name='gamma_v_w_t')
        if fixed_prices:
            model.addConstrs(p_vt[v, t] == fixed_prices.node_prices[v, t] for v in nodes for t in periods)

        epsilon_down_vwt = model.addVars(
            [(v, w, t) for v in nodes for w in list(network.neighbors(v)) for t in periods],
            lb=-GRB.INFINITY, ub=0, name='epsilon_down_v_w_t')
        epsilon_up_vwt = model.addVars([(v, w, t) for v in nodes for w in list(network.neighbors(v))
                                        for t in periods],
                                       ub=GRB.INFINITY, name='epsilon_up_v_w_t')

        r_t = model.addVars(periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='r_t')

        lambda_b = model.addVars(buyers, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='lambda_b')
        lambda_s = model.addVars(sellers, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='lambda_s')
        lambda_v_w_t = model.addVars([(v, w, t) for v in nodes for w in list(network.neighbors(v))
                                      for t in periods],
                                     lb=-GRB.INFINITY, ub=GRB.INFINITY, name='lambda_v_w_t')

        model.update()

        model.setObjective(
            gp.quicksum(lambda_b[b] for b in buyers) +
            gp.quicksum(lambda_s[s] for s in sellers) +
            gp.quicksum(lambda_v_w_t[v, w, t] for v in nodes for w in list(network.neighbors(v)) for t in periods),
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
                epsilon_down_st[s, t] * seller_min_prod_dict[s, t] * u_st[s, t]
                + epsilon_up_st[s, t] * seller_max_prod_dict[s, t] * u_st[s, t]
                + gp.quicksum(
                    epsilon_up_stl[s, t, ls] * seller_size_dict[ls][s, t] * u_st[s, t]
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
            >=
            -gp.quicksum(
                seller_no_load_cost_dict[s, t] * u_st[s, t]
                for t in periods
            )
            for s in sellers
        )
        # 3
        model.addConstrs(
            lambda_v_w_t[v, w, t]
            - epsilon_up_vwt[v, w, t] * network[v][w]['F_max']
            - epsilon_down_vwt[v, w, t] * (-network[v][w]['F_max'])
            + gamma_vwt[v, w, t] * f_vwt[v, w, t]
            >= 0
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
        # 6
        model.addConstrs(
            -gamma_vwt[v, w, t] + epsilon_up_vwt[v, w, t] + epsilon_down_vwt[v, w, t]
            == 0
            for v in nodes
            for w in list(network.neighbors(v))
            for t in periods
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

        model.optimize()

        end = time.time()
        runtime = end - start
        num_vars = model.NumVars
        num_constrs = model.NumConstrs

        status = model.getAttr('Status')

        if status == GRB.OPTIMAL:
            total_llocs = round(model.getObjective().getValue(), 2)
            llocs_buyers = round(sum(lambda_b[b].X for b in buyers), 2)
            llocs_sellers = round(sum(lambda_s[s].X for s in sellers), 2)
            llocs_network = round(
                sum(lambda_v_w_t[v, w, t].X for v in nodes for w in network.neighbors(v) for t in periods), 2)
            llocs_per_buyer = {b: round(lambda_b[b].X, 2) for b in buyers}
            llocs_per_seller = {s: round(lambda_s[s].X, 2) for s in sellers}
            llocs_per_line = {(v, w): round(sum(lambda_v_w_t[v, w, t].X for t in periods), 2)
                              for v in nodes for w in list(network.neighbors(v))}

            p_vt = {(v, t): p_vt[v, t].X for v in nodes for t in periods}
            gamma_vwt = {(v, w, t): gamma_vwt[v, w, t].X
                         for v in nodes for w in list(network.neighbors(v)) for t in periods}

            pricing = Pricing(p_vt, gamma_vwt, str(self), runtime, num_vars, num_constrs,
                              llocs=LLOCS(total_llocs, llocs_buyers, llocs_sellers, llocs_network,
                                          llocs_per_buyer, llocs_per_seller, llocs_per_line))

            if file_prices:
                write_prices(file_prices, pricing, scenario)

            return pricing

        if file_prices:
            write_prices_failure(file_prices, str(self), status)

        print(f'{self} pricing error with code {status}')

        return Error(status)

    def __str__(self):
        return 'IP'
