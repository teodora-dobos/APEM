import gurobipy as gp
from gurobipy import GRB

from code_snippets.demo.data.extraction import extract_from_buyers, extract_from_sellers
from code_snippets.demo.pricing.pricing_algorithm import PricingAlgorithm, PricingError, PricingSuccess
from code_snippets.demo.pricing.write_prices import write_prices


class IP(PricingAlgorithm):

    def compute_prices(self, allocation, market_data, file_prices="", prices=None):
        model = gp.Model('IP-Pricing')

        df_buyers = market_data.df_buyers
        df_sellers = market_data.df_sellers
        network = market_data.network
        periods = market_data.periods
        blocks_buyers = market_data.blocks_buyers
        blocks_sellers = market_data.blocks_sellers
        R_star = market_data.R_star

        nodes = network.nodes
        buyers = df_buyers['buyer'].unique().tolist()
        sellers = df_sellers['seller'].unique().tolist()

        x_bt = allocation.x_bt
        y_st = allocation.y_st
        x_btl = allocation.x_btl
        y_stl = allocation.y_stl
        f_vwt = allocation.f_vwt
        u_st = allocation.u_st

        epsilon_up_btl = model.addVars(buyers, periods, range(1, blocks_buyers + 1), ub=GRB.INFINITY,
                                       name='epsilon_up_b_t_l')
        epsilon_down_btl = model.addVars(buyers, periods, range(1, blocks_buyers + 1), lb=-GRB.INFINITY, ub=0,
                                         name='epsilon_down_b_t_l')
        epsilon_bt = model.addVars(buyers, periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='epsilon_b_t_l')
        epsilon_up_bt = model.addVars(buyers, periods, ub=GRB.INFINITY, name='epsilon_up_b_t')

        epsilon_up_stl = model.addVars(sellers, periods, range(1, blocks_sellers + 1), ub=GRB.INFINITY,
                                       name='epsilon_up_s_t_l')
        epsilon_down_stl = model.addVars(sellers, periods, range(1, blocks_sellers + 1), lb=-GRB.INFINITY, ub=0,
                                         name='epsilon_down_s_t_l')
        epsilon_st = model.addVars(sellers, periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='epsilon_s_t')
        epsilon_down_st = model.addVars(sellers, periods, lb=-GRB.INFINITY, ub=0, name='epsilon_down_s_t')
        epsilon_up_st = model.addVars(sellers, periods, ub=GRB.INFINITY, name='epsilon_up_s_t')

        p_vt = model.addVars(nodes, periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='p_vt')
        gamma_vwt = model.addVars([(v, w, t) for v in nodes for w in list(network.neighbors(v)) for t in periods],
                                  lb=-GRB.INFINITY, ub=GRB.INFINITY, name='gamma_v_w_t')
        if prices:
            model.addConstrs(p_vt[v, t] == prices.node_prices[f'p_vt[{v},{t}]'] for v in nodes for t in periods)
            model.addConstrs(gamma_vwt[v, w, t] == prices.line_congestion_prices[f'gamma_v_w_t[{v},{w},{t}]']
                             for v in nodes for w in list(network.neighbors(v)) for t in periods)

        epsilon_down_vwt = model.addVars(
            [(v, w, t) for v in nodes for w in list(network.neighbors(v)) for t in periods],
            lb=-GRB.INFINITY, ub=0, name='epsilon_down_v_w_t')
        epsilon_up_vwt = model.addVars([(v, w, t) for v in nodes for w in list(network.neighbors(v)) for t in periods],
                                       ub=GRB.INFINITY, name='epsilon_up_v_w_t')

        r_t = model.addVars(periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='r_t')

        lambda_b = model.addVars(buyers, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='lambda_b')
        lambda_s = model.addVars(sellers, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='lambda_s')
        lambda_v_w_t = model.addVars([(v, w, t) for v in nodes for w in list(network.neighbors(v)) for t in periods],
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
                epsilon_bt[b, t] * extract_from_buyers(df_buyers, 'inelastic_dem', b, t)
                + epsilon_up_bt[b, t] * extract_from_buyers(df_buyers, 'max_dem', b, t)
                + gp.quicksum(
                    epsilon_up_btl[b, t, l] * extract_from_buyers(df_buyers, 'size', b, t, l)
                    for l in range(1, blocks_buyers + 1)
                )
                for t in periods
            )
            + gp.quicksum(
                extract_from_buyers(df_buyers, 'val', b, t, l) * x_btl[f'x_btl[{b, t, l}]']
                for t in periods
                for l in range(1, blocks_buyers + 1)
            )
            - gp.quicksum(
                p_vt[extract_from_buyers(df_buyers, 'node', b, t), t] * x_bt[f'x_bt[{b, t}]']
                for t in periods
            )
            >= 0
            for b in buyers
        )
        # 2
        model.addConstrs(
            lambda_s[s]
            - gp.quicksum(
                epsilon_down_st[s, t] * extract_from_sellers(df_sellers, 'min_prod', s, t) * u_st[f'u_st[{s, t}]']
                + epsilon_up_st[s, t] * extract_from_sellers(df_sellers, 'max_prod', s, t) * u_st[f'u_st[{s, t}]']
                + gp.quicksum(
                    epsilon_up_stl[s, t, l] * extract_from_sellers(df_sellers, 'size', s, t, l) * u_st[f'u_st[{s, t}]']
                    for l in range(1, blocks_sellers + 1)
                )
                for t in periods
            )
            + gp.quicksum(
                p_vt[extract_from_sellers(df_sellers, 'node', s, t), t] * y_st[f'y_st[{s, t}]']
                for t in periods
            )
            - gp.quicksum(
                extract_from_sellers(df_sellers, 'cost', s, t, l) * y_stl[f'y_stl[{s, t, l}]']
                for t in periods
                for l in range(1, blocks_sellers + 1)
            )
            - gp.quicksum(
                extract_from_sellers(df_sellers, 'no_load_cost', s, t) * u_st[f'u_st[{s, t}]']
                for t in periods
            )
            >=
            -gp.quicksum(
                extract_from_sellers(df_sellers, 'no_load_cost', s, t) * u_st[f'u_st[{s, t}]']
                for t in periods
            )
            for s in sellers
        )
        # 3
        model.addConstrs(
            lambda_v_w_t[v, w, t]
            - epsilon_up_vwt[v, w, t] * network[v][w]['F_max']
            - epsilon_down_vwt[v, w, t] * (-network[v][w]['F_max'])
            + gamma_vwt[v, w, t] * f_vwt[f'f_vwt[{v, w, t}]']
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
            for v in nodes if v != R_star
            for t in periods
        )
        # 5
        model.addConstrs(
            r_t[t]
            + gp.quicksum(
                network[w][R_star]['B'] * (p_vt[w, t] + gamma_vwt[w, R_star, t])
                for w in nodes if R_star in list(network.neighbors(w))
            )
            - gp.quicksum(
                network[R_star][w]['B'] * (p_vt[R_star, t] + gamma_vwt[R_star, w, t])
                for w in list(network.neighbors(R_star))
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
            epsilon_up_btl[b, t, l] + epsilon_down_btl[b, t, l] - epsilon_bt[b, t]
            == extract_from_buyers(df_buyers, 'val', b, t, l)
            for b in buyers
            for t in periods
            for l in range(1, blocks_buyers + 1)
        )
        # 8
        model.addConstrs(
            epsilon_bt[b, t] + epsilon_up_bt[b, t] + p_vt[extract_from_buyers(df_buyers, 'node', b, t), t]
            == 0
            for b in buyers
            for t in periods
        )
        # 9
        model.addConstrs(
            epsilon_up_stl[s, t, l] + epsilon_down_stl[s, t, l] - epsilon_st[s, t]
            == -extract_from_sellers(df_sellers, 'cost', s, t, l)
            for s in sellers
            for t in periods
            for l in range(1, blocks_sellers + 1)
        )
        # 10
        model.addConstrs(
            epsilon_st[s, t] + epsilon_down_st[s, t] + epsilon_up_st[s, t]
            - p_vt[extract_from_sellers(df_sellers, 'node', s, t), t]
            == 0
            for s in sellers
            for t in periods
        )

        model.update()
        model.setParam("OutputFlag", 0)
        model.optimize()

        status = model.getAttr('Status')
        if status == 2:  # OPTIMAL
            status = 1
        elif status == 3:  # INFEASIBLE
            status = 2
        elif status == 4:  # INF_OR_UNBD
            status = 4
        elif status == 5:  # UNBOUNDED
            status = 5
        else:
            status = 6

        if status == 1:
            if file_prices != "":
                write_prices(p_vt, gamma_vwt, file_prices, nodes, network, periods)

            p_vt = {(v, t): p_vt[v, t].X for v in nodes for t in periods}
            gamma_vwt = {gamma_vwt[v, w, t].VarName: gamma_vwt[v, w, t].X for v in nodes for w in
                         list(network.neighbors(v))
                         for t in periods}

            return PricingSuccess(p_vt, gamma_vwt)

        return PricingError(status)
