import gurobipy as gp
from gurobipy import GRB, disposeDefaultEnv


def compute_primal_solution(df_sellers, df_buyers, network, periods, R_star, node_agents, blocks_buyers,
                            blocks_sellers, allocation_file, u_fixed=None, relaxation=False, time_out=60 * 60 * 4):
    if relaxation:
        model = gp.Model(f'DCOPF-LP')
    else:
        model = gp.Model(f'DCOPF-MILP')

    model.setParam('TimeLimit', time_out)

    nodes = network.nodes
    buyers = df_buyers['buyer'].unique().tolist()
    sellers = df_sellers['seller'].unique().tolist()

    x_bt = model.addVars(buyers, periods, name='x_bt')
    x_btl = model.addVars(buyers, periods, range(1, blocks_buyers + 1), name='x_btl')
    y_st = model.addVars(sellers, periods, name='y_st')
    y_stl = model.addVars(sellers, periods, range(1, blocks_sellers + 1), name='y_stl')

    if relaxation:
        u_st = model.addVars(sellers, periods, lb=0, ub=1, name='u_st')
    else:
        u_st = model.addVars(sellers, periods, vtype=GRB.BINARY, name='u_st')

    if u_fixed:
        model.addConstrs(u_st[s, t] == u_fixed[(s, t)] for s in sellers for t in periods if (s, t) in u_fixed.keys())

    phi_st = model.addVars(sellers, periods, lb=0, ub=GRB.INFINITY, name='phi_st')
    alpha_vt = model.addVars(nodes, periods, lb=-GRB.INFINITY, ub=GRB.INFINITY, name='alpha_vt')
    f_vwt = model.addVars([(v, w, p) for v in nodes for w in list(network.neighbors(v)) for p in periods],
                          lb=-GRB.INFINITY, ub=GRB.INFINITY, name='f_vwt')

    model.update()

    model.setObjective(
        gp.quicksum(
            df_buyers[(df_buyers['buyer'] == b) & (df_buyers['period'] == p)]['val' + str(l)].iloc[0] *
            x_btl[b, p, l]
            for b in buyers for p in periods for l in range(1, blocks_buyers + 1)) -
        gp.quicksum(df_sellers[(df_sellers['seller'] == s) & (df_sellers['period'] == p)]['cost' + str(l)].iloc[0] *
                    y_stl[s, p, l]
                    for s in sellers for p in periods for l in range(1, blocks_sellers + 1)) -
        gp.quicksum(df_sellers[(df_sellers['seller'] == s) & (df_sellers['period'] == p)]['no_load_cost'].iloc[0] *
                    u_st[s, p] for s in sellers for p in periods)
        , GRB.MAXIMIZE
    )

    # 1
    model.addConstrs((x_btl[b, p, l] >= 0
                      for b in buyers for p in periods for l in range(1, blocks_buyers + 1))
                     )
    # 2
    model.addConstrs((x_btl[b, p, l] <=
                      df_buyers[(df_buyers['buyer'] == b) & (df_buyers['period'] == p)]['size' + str(l)].iloc[0]
                      for b in buyers for p in periods for l in range(1, blocks_buyers + 1))
                     )
    # 3
    model.addConstrs((x_bt[b, p] -
                      gp.quicksum(x_btl[b, p, l] for l in range(1, blocks_buyers + 1))
                      == df_buyers[(df_buyers['buyer'] == b) & (df_buyers['period'] == p)]['inelastic_dem'].iloc[0]
                      for b in buyers for p in periods)
                     )

    # 4
    model.addConstrs((x_bt[b, p] <=
                      df_buyers[(df_buyers['buyer'] == b) & (df_buyers['period'] == p)]['max_dem'].iloc[0]
                      for b in buyers for p in periods)
                     )
    # 5
    model.addConstrs((y_stl[s, p, l] >= 0
                      for s in sellers for p in periods for l in range(1, blocks_sellers + 1))
                     )
    # 6
    model.addConstrs((y_stl[s, p, l] -
                      df_sellers[(df_sellers['seller'] == s) & (df_sellers['period'] == p)]['size' + str(l)].iloc[0] *
                      u_st[s, p] <= 0
                      for s in sellers for p in periods for l in range(1, blocks_sellers + 1))
                     )
    # 7
    model.addConstrs((y_st[s, p] -
                      gp.quicksum(y_stl[s, p, l] for l in range(1, blocks_sellers + 1))
                      == 0
                      for s in sellers for p in periods)
                     )
    # 8
    model.addConstrs((y_st[s, p] -
                      df_sellers[(df_sellers['seller'] == s) & (df_sellers['period'] == p)]['min_prod'].iloc[0] *
                      u_st[s, p] >= 0
                      for s in sellers for p in periods)
                     )
    # 9
    model.addConstrs((y_st[s, p] -
                      df_sellers[(df_sellers['seller'] == s) & (df_sellers['period'] == p)]['max_prod'].iloc[0] *
                      u_st[s, p] <= 0
                      for s in sellers for p in periods)
                     )
    # 10
    model.addConstrs((phi_st[s, p] - u_st[s, p] + u_st[s, p - 1] >= 0
                      for s in sellers for p in periods if p > 1))

    # 11
    model.addConstrs(
        (gp.quicksum(phi_st[s, i] for i in range(
            int(p - df_sellers[(df_sellers['seller'] == s) & (df_sellers['period'] == p)]['min_uptime'].iloc[0] + 1),
            int(p) + 1)) -
         u_st[s, p] <= 0
         for s in sellers for p in periods
         if p >= int(df_sellers[(df_sellers['seller'] == s) & (df_sellers['period'] == p)]['min_uptime'].iloc[0] + 1))
    )

    # 12
    model.addConstrs((f_vwt[v, w, p] >= -network[v][w]['F_max']
                      for v in nodes for w in list(network.neighbors(v)) for p in periods
                      ))
    # 13
    model.addConstrs((f_vwt[v, w, p] <= network[v][w]['F_max']
                      for v in nodes for w in list(network.neighbors(v)) for p in periods
                      ))
    # 14
    model.addConstrs((f_vwt[v, w, p] - network[v][w]['B'] * (alpha_vt[v, p] - alpha_vt[w, p]) == 0
                      for v in nodes for w in list(network.neighbors(v)) for p in periods
                      ))

    # 15 supply - demand equivalence
    model.addConstrs((gp.quicksum(y_st[s, p] for s in node_agents[v]['sellers']) -
                      gp.quicksum(x_bt[b, p] for b in node_agents[v]['buyers']) -
                      gp.quicksum(f_vwt[v, w, p] for w in list(network.neighbors(v)))
                      == 0
                      for p in periods for v in nodes), name='supply_demand')

    model.addConstrs(phi_st[s, p] >= 0 for s in sellers for p in periods)

    # 19
    model.addConstrs(alpha_vt[R_star, p] == 0 for p in periods)

    model.update()
    if not relaxation:
        model.setParam('IntegralityFocus', 1)

    model.setParam("OutputFlag", 0)

    model.optimize()
    runtime = model.runtime

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

    print("STATUS: ", status)
    if status != 4:
        obj = model.getObjective().getValue()

        shadow_prices = dict()
        if relaxation:
            for p in periods:
                for v in nodes:
                    c_pv = model.getConstrByName(f'supply_demand[{p},{v}]')
                    shadow_prices[v, p] = abs(c_pv.Pi)

        u_st_dict = dict()

        for s in sellers:
            for t in periods:
                u_st_dict[(s, t)] = u_st[s, t].X

        f = open(allocation_file, 'w+')
        f.write(f"TOTAL WELFARE: {obj}\n\n")
        for t in periods:
            welfare_per = gp.quicksum(
                df_buyers[(df_buyers['buyer'] == b) & (df_buyers['period'] == p)]['val' + str(l)].iloc[0] *
                x_btl[b, p, l].X
                for b in buyers for p in [t] for l in range(1, blocks_buyers + 1)) - gp.quicksum(
                df_sellers[(df_sellers['seller'] == s) & (df_sellers['period'] == p)]['cost' + str(l)].iloc[0] *
                y_stl[s, p, l].X
                for s in sellers for p in [t] for l in range(1, blocks_sellers + 1)) - gp.quicksum(
                df_sellers[(df_sellers['seller'] == s) & (df_sellers['period'] == p)]['no_load_cost'].iloc[0] *
                u_st[s, p].X for s in sellers for p in [t])
            f.write(f"WELFARE PERIOD {t}: {welfare_per}\n")

        x_bt = {f"x_bt[{b, t}]": x_bt[b, t].X for b in buyers for t in periods}
        x_btl = {f"x_btl[{b, t, l}]": x_btl[b, t, l].X for b in buyers for t in periods for l in
                 range(1, blocks_buyers + 1)}
        y_st = {f"y_st[{s, t}]": y_st[s, t].X for s in sellers for t in periods}
        y_stl = {f"y_stl[{s, t, l}]": y_stl[s, t, l].X for s in sellers for t in periods for l in
                 range(1, blocks_sellers + 1)}
        u_st = {f"u_st[{s, t}]": u_st[s, t].X for s in sellers for t in periods}
        f_vwt = {f"f_vwt[{v, w, t}]": f_vwt[v, w, t].X for v in nodes for w in list(network.neighbors(v)) for t in
                 periods}

        alpha_vt = {f"alpha_vt[{v, t}]": alpha_vt[v, t].X for v in nodes for t in periods}
        phi_st = {f"phi_st[{s, t}]": phi_st[s, t].X for s in sellers for t in periods}

        elastic_bids = ['size1', 'size2', 'size3']
        elastic_demand = df_buyers[elastic_bids].sum(axis=1)
        total_elastic_demand = elastic_demand.sum()

        total_inelastic_demand = df_buyers['inelastic_dem'].sum()

        f.write(f"TOTAL INELASTIC DEMAND: {total_inelastic_demand}\n")
        f.write(f"TOTAL ELASTIC DEMAND: {total_elastic_demand}\n")

        # supply_bids = ['size1', 'size2', 'size3', 'size4']
        supply_bids = ['size1', 'size2', 'size3']

        supply = df_sellers[supply_bids].sum(axis=1)
        f.write(f"TOTAL SUPPLY: {supply.sum()}\n")

        total_supply = sum(y_st[f'y_st[{s, t}]'] for s in sellers for t in periods)
        total_demand = sum(x_bt[f'x_bt[{b, t}]'] for b in buyers for t in periods)

        fulfilled_elastic_demand = sum(
            x_btl[f'x_btl[{b, t, l}]'] for b in buyers for t in periods for l in range(1, blocks_buyers + 1))

        f.write(f"FULFILLED ELASTIC DEMAND: {fulfilled_elastic_demand}\n")

        oversupply = total_supply - total_demand

        f.write(f"SUPPLY = {total_supply}\n")
        f.write(f"DEMAND = {total_demand}\n")
        f.write(f"OVERSUPPLY = {oversupply}\n")

        f.write(f"Objective: {obj}\n")
        if not relaxation:
            f.write(f"Final MIP gap value: {model.MIPGap}\n")
        f.write(f"Runtime: {runtime}\n")
        f.write(f"Nodes: {len(nodes)}\n")
        f.write(f"Branches: {len(f_vwt) / len(periods)}\n")
        f.write(f"Buyers: {len(buyers)}\n")
        f.write(f"Sellers: {len(sellers)}\n")
        f.write(f"Constraints: {len(model.getConstrs())}\n")
        f.write(f"Variables: {len(model.getVars())}\n")

        count_frac, count_binary = 0, 0
        for i in u_st.keys():
            if 0 < u_st[i] < 1:
                count_frac += 1
            else:
                count_binary += 1

        f.write(f"COUNT FRACTIONAL: {count_frac}\n")
        f.write(f"COUNT BINARY: {count_binary}\n")

        for v in model.getVars():
            f.write(f"{v.VarName} = {v.X}\n")

        f.write("\n")
        f.close()

        model.printStats()

        model.dispose()
        disposeDefaultEnv()
        del model

        return obj, status, runtime, u_st_dict, x_bt, x_btl, y_st, y_stl, u_st, f_vwt, alpha_vt, phi_st, shadow_prices

    else:
        f = open(allocation_file, 'w+')
        f.write(f"Status: {status}")
        f.close()

    model.printStats()
    model.dispose()
    disposeDefaultEnv()
    del model

    return None, None, None, status, runtime, dict(), x_bt, x_btl, y_st, y_stl, u_st, f_vwt, dict()
