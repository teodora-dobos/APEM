import gurobipy as gp
import pandas as pd
import pypsa
from gurobipy import GRB
import re
import numpy as np

# A large number to represent the cost of non-served energy (C^nse)
C_NSE = 10000  

class NodalDispatchModel:
    """
    Implements the Nodal Dispatch model (BC1) from the paper:
    "Modeling flow-based market coupling: Base case, redispatch, and unit commitment matter"
    by C. Byers and G. Hug.

    Includes verification and logging logic.
    """

    def solve(self, network: pypsa.Network, ptdf: pd.DataFrame, verbose: bool = True):
        """
        Formulates and solves the nodal dispatch problem.

        :param network: A pypsa.Network object containing generators, loads, lines, etc.
        :param ptdf: A pandas DataFrame with PTDF values (lines as index, buses as columns).
        :param verbose: If True, prints detailed verification logs.
        :return: A dictionary with result DataFrames if the problem is solved optimally,
                 otherwise None.
        """
        model = gp.Model(f'Nodal_Dispatch_BC1')
        
        model.setParam('LogToConsole', 0 if not verbose else 1)

        # --- 1. Extract Sets and Parameters from PyPSA Network ---
        snapshots = network.snapshots
        buses = network.buses.index
        lines = network.lines.index
        generators = network.generators.index

        gen_buses = network.generators.bus
        gen_costs = network.generators.marginal_cost
        startup_costs = network.generators.start_up_cost
        p_min_pu = network.generators.p_min_pu
        p_nom = network.generators.p_nom

        p_max_pu_t = network.generators_t.p_max_pu
        
        bus_demand = network.loads_t.p_set.T.groupby(network.loads.bus).sum().T
        bus_demand = bus_demand.reindex(columns=buses, fill_value=0)

        # --- 2. Define Decision Variables ---
        p_gen = model.addVars(generators, snapshots, name="p_gen", lb=0)
        u = model.addVars(generators, snapshots, vtype=GRB.BINARY, name="u")
        startup = model.addVars(generators, snapshots, vtype=GRB.BINARY, name="startup")
        shutdown = model.addVars(generators, snapshots, vtype=GRB.BINARY, name="shutdown")
        p_bus = model.addVars(buses, snapshots, lb=-GRB.INFINITY, name="p_bus")
        flow = model.addVars(lines, snapshots, lb=-GRB.INFINITY, name="flow")
        nse = model.addVars(buses, snapshots, name="nse", lb=0)
        
        # --- 3. Set Objective Function ---
        variable_costs = gp.quicksum(
            p_gen[g, t] * gen_costs[g] 
            for g in generators for t in snapshots
        )
        startup_costs_total = gp.quicksum(
            startup[g, t] * startup_costs[g] 
            for g in generators for t in snapshots
        )
        nse_costs = gp.quicksum(
            nse[b, t] * C_NSE 
            for b in buses for t in snapshots
        )
        
        model.setObjective(
            variable_costs + startup_costs_total + nse_costs, 
            GRB.MINIMIZE
        )
        
        # --- 4. Add Constraints ---
        # (3) Nodal Power Balance
        for t in snapshots:
            for b in buses:
                total_gen_at_bus = gp.quicksum(
                    p_gen[g, t] for g in gen_buses[gen_buses == b].index
                )
                model.addConstr(
                    p_bus[b, t] == total_gen_at_bus - bus_demand.at[t, b] + nse[b, t],
                    name=f"power_balance_{b}_{t}"
                )

        # (4) System-wide balance
        for t in snapshots:
            model.addConstr(
                gp.quicksum(p_bus[b, t] for b in buses) == 0,
                name=f"system_balance_{t}"
            )
        
        # (6) DC Power Flow Calculation
        for t in snapshots:
            for l in lines:
                line_flow_calc = gp.quicksum(ptdf.at[l, b] * p_bus[b, t] for b in buses)
                model.addConstr(
                    flow[l, t] == line_flow_calc,
                    name=f"dc_power_flow_{l}_{t}"
                )
                
        # (5) Line Flow Limits
        for t in snapshots:
            for l in lines:
                limit = network.lines.at[l, 's_nom']
                model.addConstr(flow[l, t] <= limit, name=f"line_limit_upper_{l}_{t}")
                model.addConstr(flow[l, t] >= -limit, name=f"line_limit_lower_{l}_{t}")

        # (1) Generator Operating Constraints
        for g in generators:
            for t in snapshots:
                model.addConstr(
                    p_gen[g, t] >= p_min_pu[g] * p_nom[g] * u[g, t],
                    name=f"gen_min_prod_{g}_{t}"
                )
                
                model.addConstr(
                    p_gen[g, t] <= p_max_pu_t.at[t, g] * p_nom[g] * u[g, t],
                    name=f"gen_max_prod_{g}_{t}"
                )
                
                # Unit commitment logic
                if t == snapshots[0]:
                    model.addConstr(u[g, t] == startup[g, t], name=f"startup_logic_initial_{g}")
                    model.addConstr(shutdown[g, t] == 0, name=f"no_shutdown_initial_{g}")
                else:
                    t_prev = snapshots[snapshots.get_loc(t) - 1]
                    model.addConstr(u[g, t] - u[g, t_prev] == startup[g, t] - shutdown[g, t], name=f"uc_logic_{g}_{t}")

                model.addConstr(startup[g, t] + shutdown[g, t] <= 1, name=f"startup_shutdown_excl_{g}_{t}")

        for t in snapshots:
            for b in buses:
                 model.addConstr(nse[b, t] <= bus_demand.at[t, b], name=f"nse_limit_{b}_{t}")

        # --- 5. Solve and Prepare Results ---
        model.optimize()

        if model.Status == GRB.OPTIMAL:
            print(f"Optimal MILP solution found. Total Cost: {model.ObjVal:.2f}")

            p_gen_optimal = pd.DataFrame({g: {t: p_gen[g, t].X for t in snapshots} for g in generators})
            u_optimal = pd.DataFrame({g: {t: u[g, t].X for t in snapshots} for g in generators})
            p_bus_optimal = pd.DataFrame({b: {t: p_bus[b, t].X for t in snapshots} for b in buses})
            flow_optimal = pd.DataFrame({l: {t: flow[l, t].X for t in snapshots} for l in lines})
            nse_optimal = pd.DataFrame({b: {t: nse[b, t].X for t in snapshots} for b in buses})

            startup_optimal = pd.DataFrame({g: {t: startup[g, t].X for t in snapshots} for g in generators})
            

            all_vars_for_saving = [{"variable": v.VarName, "value": v.X} for v in model.getVars()]

            # --- 6. Fix binary variables to get duals ---
            for v in model.getVars():
                if v.VType in (GRB.BINARY, GRB.INTEGER):
                    v.LB = v.X
                    v.UB = v.X
            
            # Relax to an LP to get duals
            relaxed_model = model.relax()
            relaxed_model.setParam('LogToConsole', 0)
            relaxed_model.optimize()
            
            if relaxed_model.Status != GRB.OPTIMAL:
                 print("Warning: LP re-solve for duals failed. Prices will be incorrect.")
                 nodal_prices = pd.DataFrame(0, index=snapshots, columns=buses)
            else:
                nodal_prices = pd.DataFrame({
                    b: {t: relaxed_model.getConstrByName(f"power_balance_{b}_{t}").Pi for t in snapshots} 
                    for b in buses
                })

            results = {
                "objective_value": model.ObjVal,
                "p_gen": p_gen_optimal,
                "u": u_optimal,
                "p_bus": p_bus_optimal,
                "flow": flow_optimal,
                "nse": nse_optimal,
                "startup": startup_optimal,
                "duals": {"nodal_price": nodal_prices},
                "model" : model,
                "all_vars": all_vars_for_saving
            }
            
            return results
        else:
            print(f"Optimization failed with status code: {model.Status}")
            model.computeIIS()
            model.write("model_iis.ilp")
            print("Irreducible Inconsistent Subsystem (IIS) written to model_iis.ilp")
            return None

    def __str__(self):
        return 'Nodal_Dispatch_Model'