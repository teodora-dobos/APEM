import pypsa
import pandas as pd
import numpy as np
import gurobipy as gp
from gurobipy import GRB
import logging

# --- Setup a dedicated logger for this module ---
# This will create a file named 'zonal_dispatch_debug.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='zonal_dispatch_debug.log',
    filemode='w'
)

# High penalty for non-served energy, consistent with the paper's approach
C_NSE = 10000
# A high penalty cost for deviating from the zonal schedule in Redispatch R1
C_DEV = 99999 

# ==============================================================================
# === 1. HELPER FUNCTIONS FOR ZONAL CALCULATIONS
# ==============================================================================

def get_zone_maps(network: pypsa.Network, node_zone_mapper: callable, zonal_configuration: str):
    """
    Creates mappings from nodes to zones and zones to nodes using the provided mapper function.
    """
    node_to_zone = pd.Series(
        {bus: node_zone_mapper(zonal_configuration, network.buses.at[bus, 'x'], network.buses.at[bus, 'y'])
         for bus in network.buses.index},
        name="zone"
    ).dropna().astype(int)
    
    zone_to_nodes = node_to_zone.groupby(node_to_zone).apply(lambda group: group.index.tolist()).to_dict()
    return node_to_zone, zone_to_nodes

def calculate_gsk(network: pypsa.Network, node_to_zone: pd.Series, zone_to_nodes: dict) -> pd.Series:
    """Calculates Generation Shift Keys (GSK) based on generator p_nom."""
    gen_p_nom = network.generators.groupby('bus')['p_nom'].sum()
    bus_p_nom = gen_p_nom.reindex(network.buses.index, fill_value=0)
    gsk = pd.Series(index=network.buses.index, dtype=float)
    for zone_id, nodes_in_zone in zone_to_nodes.items():
        zone_total_p_nom = bus_p_nom.loc[nodes_in_zone].sum()
        if zone_total_p_nom > 1e-6:
            gsk.loc[nodes_in_zone] = bus_p_nom.loc[nodes_in_zone] / zone_total_p_nom
        else: # Handle zones with no generation capacity by distributing evenly
            num_nodes = len(nodes_in_zone)
            if num_nodes > 0: gsk.loc[nodes_in_zone] = 1.0 / num_nodes
            else: gsk.loc[nodes_in_zone] = 0.0
    return gsk

def calculate_zonal_ptdf(nodal_ptdf: pd.DataFrame, gsk: pd.Series, node_to_zone: pd.Series) -> pd.DataFrame:
    """Calculates the Zonal PTDF matrix."""
    return nodal_ptdf.mul(gsk, axis='columns').T.groupby(node_to_zone).sum().T

def select_fb_lines(zonal_ptdf: pd.DataFrame, network: pypsa.Network, node_to_zone: pd.Series, threshold: float = 0.05) -> list:
    """Selects lines for the Flow-Based domain (interzonal + sensitive intrazonal)."""
    interzonal_lines = {
        line for line, data in network.lines.iterrows()
        if node_to_zone.get(data.bus0) != node_to_zone.get(data.bus1)
    }
    ptdf_impact = zonal_ptdf.max(axis=1) - zonal_ptdf.min(axis=1)
    sensitive_intrazonal_lines = set(ptdf_impact[ptdf_impact > threshold].index)
    return sorted(list(interzonal_lines | sensitive_intrazonal_lines))

def aggregate_by_zone(df: pd.DataFrame, node_to_zone: pd.Series) -> pd.DataFrame:
    """Aggregates a nodal DataFrame (like demand or net positions) to the zonal level."""
    return df.T.groupby(node_to_zone).sum().T

# ==============================================================================
# === 2. BASE CASE GENERATOR (Reference Nodal Positions)
# ==============================================================================
class BaseCaseGenerator:
    def __init__(self, network: pypsa.Network, ptdf: pd.DataFrame, 
                 node_zone_mapper: callable, zonal_configuration: str):
        self.network = network
        self.ptdf = ptdf
        self.node_to_zone, self.zone_to_nodes = get_zone_maps(network, node_zone_mapper, zonal_configuration)
        self.snapshots = network.snapshots
        self.buses = network.buses.index
        self.lines = network.lines.index
        self.generators = network.generators.index

    def _create_base_nodal_model(self, network_instance: pypsa.Network):
        """Helper to create the nodal unit commitment model for base case generation."""
        model = gp.Model('BaseCaseNodal')
        model.setParam('LogToConsole', 0)

        # Extract parameters from the (potentially modified) network instance
        gen_buses = network_instance.generators.bus
        gen_costs = network_instance.generators.marginal_cost
        startup_costs = network_instance.generators.start_up_cost
        p_min_pu = network_instance.generators.p_min_pu
        p_max_pu_t = network_instance.generators_t.p_max_pu
        p_nom = network_instance.generators.p_nom
        bus_demand = network_instance.loads_t.p_set.T.groupby(network_instance.loads.bus).sum().T
        bus_demand = bus_demand.reindex(columns=self.buses, fill_value=0)

        # Decision Variables (as per Nodal Model, Eqs. 2-6)
        p_gen = model.addVars(self.generators, self.snapshots, name="p_gen", lb=0)
        u = model.addVars(self.generators, self.snapshots, vtype=GRB.BINARY, name="u")
        startup = model.addVars(self.generators, self.snapshots, vtype=GRB.BINARY, name="startup")
        shutdown = model.addVars(self.generators, self.snapshots, vtype=GRB.BINARY, name="shutdown")
        p_bus = model.addVars(self.buses, self.snapshots, lb=-GRB.INFINITY, name="p_bus")
        flow = model.addVars(self.lines, self.snapshots, lb=-GRB.INFINITY, name="flow")
        nse = model.addVars(self.buses, self.snapshots, name="nse", lb=0)

        # Eq. (2) - Objective Function
        objective = (gp.quicksum(p_gen[g, t] * gen_costs[g] for g, t in p_gen) +
                     gp.quicksum(startup[g, t] * startup_costs[g] for g, t in startup) +
                     gp.quicksum(nse[b, t] * C_NSE for b, t in nse))
        model.setObjective(objective, GRB.MINIMIZE)
        
        # --- Base Constraints (Eqs. 1, 3, 4, 5, 6) ---
        # Eq. (3) - Nodal power balance
        model.addConstrs((p_bus[b, t] == gp.quicksum(p_gen[g, t] for g in gen_buses[gen_buses == b].index) - bus_demand.at[t, b] + nse[b, t]
                          for b in self.buses for t in self.snapshots), name="power_balance")
        # Eq. (4) - System-wide power balance
        model.addConstrs((gp.quicksum(p_bus[b, t] for b in self.buses) == 0 for t in self.snapshots), name="system_balance")
        # Eq. (6) - DC power flow calculation
        model.addConstrs((flow[l, t] == gp.quicksum(self.ptdf.at[l, b] * p_bus[b, t] for b in self.buses)
                          for l in self.lines for t in self.snapshots), name="dc_flow")
        # Eq. (5) - Line flow limits
        model.addConstrs((flow[l, t] <= network_instance.lines.at[l, 's_nom'] for l, t in flow), name="flow_upper")
        model.addConstrs((flow[l, t] >= -network_instance.lines.at[l, 's_nom'] for l, t in flow), name="flow_lower")
        # Eq. (1) - Generator constraints (set P)
        for g in self.generators:
            for t_idx, t in enumerate(self.snapshots):
                model.addConstr(p_gen[g, t] >= p_min_pu[g] * p_nom[g] * u[g, t])
                model.addConstr(p_gen[g, t] <= p_max_pu_t.at[t, g] * p_nom[g] * u[g, t])
                if t_idx > 0: model.addConstr(u[g, t] - u[g, self.snapshots[t_idx-1]] == startup[g, t] - shutdown[g, t])
                else: model.addConstr(u[g, t] == startup[g, t]); model.addConstr(shutdown[g, t] == 0)
                model.addConstr(startup[g, t] + shutdown[g, t] <= 1)
        model.addConstrs((nse[b, t] <= bus_demand.at[t,b] for b, t in nse), name="nse_limit")
        return model, p_bus

    def generate(self, base_case_type: str):
        """Generates a base case for expected nodal net positions (p_bus_expected)."""
        logging.info(f"--- Generating Base Case for: {base_case_type} ---")
        if base_case_type == 'BC1': # Same as nodal solution
            model, p_bus = self._create_base_nodal_model(self.network)
        elif base_case_type == 'BC2': # Eq. (9)
            model, p_bus = self._create_base_nodal_model(self.network)
            for t in self.snapshots:
                for zone_id, nodes in self.zone_to_nodes.items():
                    model.addConstr(gp.quicksum(p_bus[b, t] for b in nodes) == 0, name=f"zonal_net_pos_zero_{zone_id}_{t}")
        elif base_case_type == 'BC3.1': # Eq. (10)
            net_mod = self.network.copy()
            net_mod.loads_t.p_set *= 1.2
            model, p_bus = self._create_base_nodal_model(net_mod)
        elif base_case_type == 'BC3.2': # Eq. (11)
            net_mod = self.network.copy()
            perturbation = 1 + (np.random.rand(*net_mod.loads_t.p_set.shape) * 0.4 - 0.2)
            net_mod.loads_t.p_set *= perturbation
            model, p_bus = self._create_base_nodal_model(net_mod)
        elif base_case_type == 'BC4': # Eq. (12)
            net_relaxed = self.network.copy()
            for line_name, line_data in net_relaxed.lines.iterrows():
                if self.node_to_zone.get(line_data.bus0) == self.node_to_zone.get(line_data.bus1):
                    net_relaxed.lines.at[line_name, 's_nom'] *= 10
            relaxed_model, relaxed_p_bus = self._create_base_nodal_model(net_relaxed)
            relaxed_model.optimize()
            if relaxed_model.Status != GRB.OPTIMAL: raise Exception("BC4 Step 1 (relaxed) failed.")
            p_bus_relaxed = pd.DataFrame({b: {t: relaxed_p_bus[b, t].X for t in self.snapshots} for b in self.buses})
            p_tz_ref = aggregate_by_zone(p_bus_relaxed, self.node_to_zone)
            model, p_bus = self._create_base_nodal_model(self.network)
            for t in self.snapshots:
                for zone_id, nodes in self.zone_to_nodes.items():
                    model.addConstr(gp.quicksum(p_bus[b, t] for b in nodes) == p_tz_ref.at[t, zone_id], name=f"zonal_net_pos_fixed_{zone_id}_{t}")
        else: raise ValueError(f"Unknown base_case_type: {base_case_type}")

        model.optimize()
        if model.Status == GRB.OPTIMAL:
            logging.info(f"Base Case {base_case_type} solved successfully.")
            return pd.DataFrame({b: {t: p_bus[b, t].X for t in self.snapshots} for b in self.buses})
        else:
            logging.error(f"Base Case Generation for {base_case_type} FAILED. IIS written to file.");
            model.computeIIS(); model.write(f"base_case_{base_case_type}_iis.ilp")
            return None

# ==============================================================================
# === 3. ZONAL DISPATCH MODEL (Flow-Based Market Coupling)
# ==============================================================================
class ZonalDispatchModel:
    def solve(self, network: pypsa.Network, nodal_ptdf: pd.DataFrame, 
              p_bus_expected: pd.DataFrame, node_zone_mapper: callable,
              zonal_configuration: str, verbose: bool = True):
        
        logging.info("--- Starting ZonalDispatchModel solve ---")
        model = gp.Model('Zonal_Dispatch_FBMC'); model.setParam('LogToConsole', 1 if verbose else 0)

        # --- 1. Zonal Pre-calculations ---
        node_to_zone, zone_to_nodes = get_zone_maps(network, node_zone_mapper, zonal_configuration)
        zones = sorted(zone_to_nodes.keys())
        buses_in_zones = node_to_zone.index
        nodal_ptdf = nodal_ptdf.loc[:, buses_in_zones]
        p_bus_expected = p_bus_expected.loc[:, buses_in_zones]
        gsk = calculate_gsk(network, node_to_zone, zone_to_nodes)
        zonal_ptdf = calculate_zonal_ptdf(nodal_ptdf, gsk, node_to_zone)
        L_z = select_fb_lines(zonal_ptdf, network, node_to_zone, threshold=0.05)
        
        bus_demand = network.loads_t.p_set.T.groupby(network.loads.bus).sum().T.reindex(columns=network.buses.index, fill_value=0)
        zonal_demand = aggregate_by_zone(bus_demand, node_to_zone)
        p_tz_expected = aggregate_by_zone(p_bus_expected, node_to_zone)
        flow_expected_nodal = nodal_ptdf.dot(p_bus_expected.T).T
        flow_expected_zonal = zonal_ptdf.dot(p_tz_expected.T).T
        delta_F = flow_expected_nodal - flow_expected_zonal # Eq. (16) correction term

        # --- 2. Define Model Variables & Objective ---
        snapshots, generators = network.snapshots, network.generators.index
        p_gen = model.addVars(generators, snapshots, name="p_gen", lb=0)
        u = model.addVars(generators, snapshots, vtype=GRB.BINARY, name="u")
        startup = model.addVars(generators, snapshots, vtype=GRB.BINARY, name="startup")
        shutdown = model.addVars(generators, snapshots, vtype=GRB.BINARY, name="shutdown")
        p_tz = model.addVars(zones, snapshots, lb=-GRB.INFINITY, name="p_tz")
        nse_tz = model.addVars(zones, snapshots, name="nse_tz", lb=0)
        flow_zonal = model.addVars(L_z, snapshots, lb=-GRB.INFINITY, name="flow_zonal")

        # Objective Function - Eq. (13)
        gen_costs, startup_c = network.generators.marginal_cost, network.generators.start_up_cost
        objective = (gp.quicksum(p_gen[g, t] * gen_costs[g] for g, t in p_gen) +
                     gp.quicksum(startup[g, t] * startup_c[g] for g, t in startup) +
                     gp.quicksum(nse_tz[z, t] * C_NSE for z, t in nse_tz))
        model.setObjective(objective, GRB.MINIMIZE)

        # --- 3. Define Model Constraints ---
        # Generator constraints (similar to Eq. 1)
        gen_to_zone = network.generators.bus.map(node_to_zone).dropna()
        p_min_pu, p_nom = network.generators.p_min_pu, network.generators.p_nom
        p_max_pu_t = network.generators_t.p_max_pu
        for g in generators:
            for t_idx, t in enumerate(snapshots):
                model.addConstr(p_gen[g, t] >= p_min_pu[g] * p_nom[g] * u[g, t])
                model.addConstr(p_gen[g, t] <= p_max_pu_t.at[t,g] * p_nom[g] * u[g, t]) # CORRECTED
                if t_idx > 0: model.addConstr(u[g, t] - u[g, snapshots[t_idx-1]] == startup[g, t] - shutdown[g, t])
                else: model.addConstr(u[g, t] == startup[g, t]); model.addConstr(shutdown[g, t] == 0)

        # Zonal Power Balance - Eq. (14)
        for t in snapshots:
            for z in zones:
                gens_in_zone = gen_to_zone[gen_to_zone == z].index
                model.addConstr(gp.quicksum(p_gen[g,t] for g in gens_in_zone) - p_tz[z,t] + nse_tz[z,t] == zonal_demand.at[t,z], name=f"zonal_balance_{z}_{t}")
        # System-wide zonal balance - Eq. (15)
        model.addConstrs((gp.quicksum(p_tz[z, t] for z in zones) == 0 for t in snapshots), name="system_zonal_balance")
        # Zonal flow calculation & limits - Eq. (16), (17), (18)
        model.addConstrs((flow_zonal[l, t] == gp.quicksum(zonal_ptdf.at[l, z] * p_tz[z, t] for z in zones) for l,t in flow_zonal), name="zonal_flow_calc")
        model.addConstrs((flow_zonal[l, t] <= network.lines.at[l, 's_nom'] - delta_F.at[t, l] for l,t in flow_zonal), name="zonal_flow_upper")
        model.addConstrs((flow_zonal[l, t] >= -network.lines.at[l, 's_nom'] - delta_F.at[t, l] for l,t in flow_zonal), name="zonal_flow_lower")
        model.addConstrs((nse_tz[z, t] <= zonal_demand.at[t, z] for z,t in nse_tz), name="nse_limit_zonal")

        # --- 4. Solve and Prepare Results ---
        model.optimize()
        if model.Status == GRB.OPTIMAL:
            # Fix integer variables and re-solve as LP to get duals
            for v in model.getVars():
                if v.VType in (GRB.BINARY, GRB.INTEGER): v.LB = v.X; v.UB = v.X
            relaxed = model.relax(); relaxed.setParam('LogToConsole', 0); relaxed.optimize()
            
            return {
                "objective_value": model.ObjVal,
                "p_gen": pd.DataFrame({g: {t: p_gen[g, t].X for t in snapshots} for g in generators}),
                "p_tz": pd.DataFrame({z: {t: p_tz[z, t].X for t in snapshots} for z in zones}),
                "u": pd.DataFrame({g: {t: u[g, t].X for t in snapshots} for g in generators}),
                "nse_tz": pd.DataFrame({z: {t: nse_tz[z, t].X for t in snapshots} for z in zones}),
                "duals": { "zonal_price": pd.DataFrame({z: {t: relaxed.getConstrByName(f"zonal_balance_{z}_{t}").Pi for t in snapshots} for z in zones})}
            }
        else:
            logging.error(f"Zonal MILP failed. IIS written to zonal_model_iis.ilp")
            model.computeIIS(); model.write("zonal_model_iis.ilp")
            return None

# ==============================================================================
# === 4. POST-ZONAL REDISPATCH MODEL
# ==============================================================================
class RedispatchModel:
    def solve(self, network: pypsa.Network, ptdf: pd.DataFrame,
              zonal_results: dict, node_zone_mapper: callable,
              zonal_configuration: str, method: str, verbose: bool = True):

        logging.info(f"--- Starting RedispatchModel solve (Method: {method}) ---")
        if method not in ['R1', 'R2']: raise ValueError("Method must be 'R1' or 'R2'")
        model = gp.Model(f'Redispatch_{method}'); model.setParam('LogToConsole', 1 if verbose else 0)

        # --- 1. Extract Sets, Parameters, and Schedules ---
        node_to_zone, _ = get_zone_maps(network, node_zone_mapper, zonal_configuration)
        snapshots, buses, lines, generators = network.snapshots, network.buses.index, network.lines.index, network.generators.index
        p_gen_zonal, u_zonal = zonal_results['p_gen'], zonal_results['u']

        # --- 2. Define Decision Variables ---
        p_gen = model.addVars(generators, snapshots, name="p_gen_rd", lb=0)
        u = model.addVars(generators, snapshots, vtype=GRB.BINARY, name="u_rd")
        startup = model.addVars(generators, snapshots, vtype=GRB.BINARY, name="startup_rd")
        shutdown = model.addVars(generators, snapshots, vtype=GRB.BINARY, name="shutdown_rd")
        p_bus = model.addVars(buses, snapshots, lb=-GRB.INFINITY, name="p_bus_rd")
        nse = model.addVars(buses, snapshots, name="nse_rd", lb=0)
        
        gen_costs, startup_costs = network.generators.marginal_cost, network.generators.start_up_cost

        # --- 3. Set Objective Function based on Method ---
        if method == 'R1':
            # Eq. (19) - Minimize total operating cost + deviation penalty
            delta_tz = model.addVars(zonal_results['p_tz'].columns, snapshots, lb=0, name="delta_tz")
            op_costs = (gp.quicksum(p_gen[g, t] * gen_costs[g] for g,t in p_gen) +
                        gp.quicksum(startup[g, t] * startup_costs[g] for g,t in startup) +
                        gp.quicksum(nse[b, t] * C_NSE for b,t in nse))
            deviation_penalty = gp.quicksum(delta_tz[z, t] * C_DEV for z,t in delta_tz)
            model.setObjective(op_costs + deviation_penalty, GRB.MINIMIZE)
            
        elif method == 'R2':
            # Eq. (20) - Minimize redispatch compensation costs
            p_up = model.addVars(generators, snapshots, name="p_up", lb=0)
            p_down = model.addVars(generators, snapshots, name="p_down", lb=0)
            model.addConstrs((p_gen[g, t] - p_gen_zonal.at[t, g] == p_up[g, t] - p_down[g, t] for g, t in p_gen), name="redispatch_delta_definition")

            zonal_prices = zonal_results['duals']['zonal_price']
            gen_zones = network.generators.bus.map(node_to_zone)
            gen_prices = pd.Series({g: zonal_prices.at[snapshots[0], gen_zones[g]] for g in generators})
            
            cost_up_reg = gp.quicksum(p_up[g, t] * gen_costs[g] for g, t in p_up)
            profit_margin = (gen_prices - gen_costs).clip(lower=0)
            cost_down_reg = gp.quicksum(p_down[g, t] * profit_margin[g] for g, t in p_down)
            cost_new_startup = gp.quicksum(startup[g, t] * startup_costs[g] for g, t in startup if u_zonal.at[t, g] < 0.5)
            cost_nse = gp.quicksum(nse[b, t] * C_NSE for b, t in nse)
            model.setObjective(cost_up_reg + cost_down_reg + cost_new_startup + cost_nse, GRB.MINIMIZE)

        # --- 4. Add Nodal Redispatch Constraints ---
        bus_demand = network.loads_t.p_set.T.groupby(network.loads.bus).sum().T.reindex(columns=buses, fill_value=0)
        
        # Eq. (23) -> Nodal Power Balance
        model.addConstrs((p_bus[b, t] == gp.quicksum(p_gen[g, t] for g in network.generators.index[network.generators.bus == b]) - bus_demand.at[t, b] + nse[b, t] 
                          for b in buses for t in snapshots), name="redispatch_balance")
        # Eq. (4) -> System-wide balance
        model.addConstrs((gp.quicksum(p_bus[b, t] for b in buses) == 0 for t in snapshots), name="redispatch_sys_balance")
        
        # Eq. (25) & (6) -> Nodal flow calculation and limits
        model.addConstrs((gp.quicksum(ptdf.at[l, b] * p_bus[b,t] for b in ptdf.columns) <= network.lines.at[l, 's_nom'] for l in lines for t in snapshots), name="redispatch_flow_upper")
        model.addConstrs((gp.quicksum(ptdf.at[l, b] * p_bus[b,t] for b in ptdf.columns) >= -network.lines.at[l, 's_nom'] for l in lines for t in snapshots), name="redispatch_flow_lower")
        
        # Part of set P in Eq. (19) -> Generator operating constraints
        p_min_pu, p_nom = network.generators.p_min_pu, network.generators.p_nom
        p_max_pu_t = network.generators_t.p_max_pu
        for g in generators:
            for t in snapshots:
                model.addConstr(p_gen[g, t] >= p_min_pu[g] * p_nom[g] * u[g, t])
                model.addConstr(p_gen[g, t] <= p_max_pu_t.at[t, g] * p_nom[g] * u[g, t])
                u_previous = u_zonal.at[t, g]
                model.addConstr(u[g, t] - u_previous == startup[g, t] - shutdown[g, t], name=f"uc_logic_{g}_{t}")
                model.addConstr(startup[g, t] + shutdown[g, t] <= 1)

        # Eq. (22) -> Fixed commitment for slow units
        slow_carriers = ['nuclear', 'lignite', 'coal', 'oil']
        slow_gens = network.generators[network.generators.carrier.isin(slow_carriers)].index
        model.addConstrs((u[g,t] == u_zonal.at[t,g] for g in slow_gens for t in snapshots), name="fixed_slow_uc")
        
        # Eq. (21) -> Deviation calculation (only for R1 method)
        if method == 'R1':
            for t in snapshots:
                for z, nodes in get_zone_maps(network, node_zone_mapper, zonal_configuration)[1].items():
                    p_bus_in_zone = gp.quicksum(p_bus[b, t] for b in nodes)
                    model.addConstr(delta_tz[z, t] >= p_bus_in_zone - zonal_results['p_tz'].at[t, z], name=f"dev_pos_{z}_{t}")
                    model.addConstr(delta_tz[z, t] >= -(p_bus_in_zone - zonal_results['p_tz'].at[t, z]), name=f"dev_neg_{z}_{t}")

        # --- 5. Solve and Prepare Results ---
        model.optimize()
        if model.Status == GRB.OPTIMAL:
            p_gen_redispatch = pd.DataFrame({g: {t: p_gen[g, t].X for t in snapshots} for g in generators})
            startup_redispatch = pd.DataFrame({g: {t: startup[g, t].X > 0.5 for t in snapshots} for g in generators})
            nse_redispatch = pd.DataFrame({b: {t: nse[b, t].X for t in snapshots} for b in buses})
            
            redispatch_cost = model.ObjVal
            startup_cost_total = (startup_redispatch * startup_costs).sum().sum()
            
            final_operating_cost = ((p_gen_redispatch * gen_costs).sum().sum() + startup_cost_total + (nse_redispatch.sum().sum() * C_NSE))
            return {
                            "method": method,
                            "status": "Optimal",
                            "redispatch_cost": redispatch_cost,
                            "final_operating_cost": final_operating_cost,
                            "p_gen_redispatch": p_gen_redispatch,
                            "nse_redispatch": nse_redispatch,
                            "startup_redispatch": startup_redispatch
                        }
        else:
            model.computeIIS(); model.write(f"redispatch_{method}_iis.ilp")
            return {"status": "Failed", "method": method}