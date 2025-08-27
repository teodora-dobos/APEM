import pandas as pd
import gurobipy as gp
from gurobipy import GRB 
import pypsa
import networkx as nx
from types import SimpleNamespace
from apem.allocation.algorithms.nodal_clearing.nodal_fbmc import NodalDispatchModel
from apem.allocation.allocation import Allocation
from apem.data.parsing.scenario import Scenario



# C_NSE should be consistent with the value in your NodalDispatchModel
C_NSE = 10000 

def create_allocation_from_nodal_results(nodal_results, network, scenario, power_flow_model):
    """
    Converts results from the NodalDispatchModel into an APEM Allocation object.

    This function is specifically designed to handle a mismatch between integer 'seller'
    IDs in the APEM scenario and string 'generator' names used in the PyPSA model results.
    It creates a mapping to correctly translate between them.

    :param nodal_results: Dictionary from NodalDispatchModel.solve(), containing result 
                          DataFrames and the Gurobi model.
    :param network: The PyPSA network object used for the simulation.
    :param scenario: The input APEM Scenario object.
    :param power_flow_model: The instance of the power flow model (e.g., NodalFBMC) that was run.
    :return: An Allocation object containing the detailed results.
    :raises ValueError: If the model in nodal_results was not solved to optimality.
    """
    model = nodal_results.get('model')
    if model is None or model.Status != GRB.OPTIMAL:
        raise ValueError("Cannot create allocation from a non-optimally solved or missing model.")

    # --- 1. Extract result DataFrames and create identifier mappings ---
    p_gen_df = nodal_results['p_gen']        # Results indexed by string 'generator' name
    u_df = nodal_results['u']                
    startup_df = nodal_results['startup']    
    flow_df = nodal_results['flow']          
    nse_df = nodal_results['nse']            
    duals_df = nodal_results['duals']['nodal_price'] 

    periods = scenario.periods
    snapshot_to_period = {snap: p for p, snap in zip(periods, network.snapshots)}

    # The scenario contains both identifiers. We use it as the bridge.
    mapping_df = scenario.df_sellers[['seller', 'generator']].drop_duplicates()
    gen_name_to_seller_id = pd.Series(mapping_df.seller.values, index=mapping_df.generator).to_dict()

    # --- 2. Convert supply-side results (y_st, u_st, phi_st) using the mapping ---
    y_st, u_st, phi_st = {}, {}, {}

    # Iterate over the results (which use string names) and map them to the integer IDs
    for gen_name in p_gen_df.columns:
        seller_id = gen_name_to_seller_id.get(gen_name)
        if seller_id is None:
            continue # Skip if a generator from model is not in our mapping

        for snapshot in p_gen_df.index:
            period = snapshot_to_period[snapshot]
            y_st[(seller_id, period)] = p_gen_df.loc[snapshot, gen_name]
            u_st[(seller_id, period)] = round(u_df.loc[snapshot, gen_name])
            phi_st[(seller_id, period)] = startup_df.loc[snapshot, gen_name]

    # Reconstruct block-level supply (y_stl) assuming a single block
    y_stl = {
        (s, t, 1): val for (s, t), val in y_st.items()
    }

    # --- 3. Convert network results (f_vwt, alpha_vt) ---
    alpha_vt = {
        (bus, snapshot_to_period[t]): duals_df.loc[t, bus]
        for bus in duals_df.columns for t in duals_df.index
    }
    
    f_vwt = {}
    for line_name, flows_over_time in flow_df.items():
        line_info = network.lines.loc[line_name]
        v, w = line_info.bus0, line_info.bus1
        for snapshot, flow in flows_over_time.items():
            t = snapshot_to_period[snapshot]
            f_vwt[(v, w, t)] = flow
            f_vwt[(w, v, t)] = -flow

    # --- 4. Reconstruct demand-side results (x_bt, x_btl) ---
    # (This section is also unaffected by the seller/generator ID mismatch)
    x_bt, x_btl = {}, {}
    bus_demand_df = network.loads_t.p_set.T.groupby(network.loads.bus).sum().T

    for bus_name, nse_at_bus in nse_df.items():
        buyers_at_bus = scenario.nodes_agents.get(bus_name, {}).get('buyers', [])
        if not buyers_at_bus:
            continue
            
        for snapshot, nse_val in nse_at_bus.items():
            t = snapshot_to_period[snapshot]
            total_bus_demand = bus_demand_df.loc[snapshot, bus_name]
            
            if total_bus_demand <= 1e-6:
                for b in buyers_at_bus:
                    x_bt[(b, t)] = 0
                continue
            
            served_ratio = 1.0 - (nse_val / total_bus_demand)
            
            for b in buyers_at_bus:
                buyer_info = scenario.df_buyers[
                    (scenario.df_buyers['buyer'] == b) & (scenario.df_buyers['period'] == t)
                ]
                
                original_demand = buyer_info['inelastic_dem'].sum() + buyer_info[[f'size_{lb}' for lb in scenario.blocks_buyers]].sum().sum()
                
                accepted_demand = original_demand * served_ratio
                x_bt[(b, t)] = accepted_demand
                
                remaining_demand = accepted_demand - buyer_info['inelastic_dem'].iloc[0]
                for lb in scenario.blocks_buyers:
                    block_size = buyer_info[f'size_{lb}'].iloc[0]
                    accepted_block_demand = min(max(0, remaining_demand), block_size)
                    x_btl[(b, t, lb)] = accepted_block_demand
                    remaining_demand -= accepted_block_demand

    # --- 5. Calculate Welfare ---
    total_demand = bus_demand_df.sum().sum()
    total_nse = nse_df.sum().sum()
    value_of_served_energy = C_NSE * (total_demand - total_nse)
    total_production_cost = model.ObjVal - (C_NSE * total_nse)
    welfare = value_of_served_energy - total_production_cost

    # --- 6. Instantiate and return the Allocation object ---
    allocation = Allocation(
        welfare=welfare,
        x_bt=x_bt,
        y_st=y_st,
        x_btl=x_btl,
        y_stl=y_stl,
        f_vwt=f_vwt,
        alpha_vt=alpha_vt,
        u_st=u_st,
        phi_st=phi_st,
        power_flow_model=power_flow_model,
        runtime=model.Runtime,
        num_vars=model.NumVars,
        num_constrs=model.NumConstrs,
        MIP_gap=model.MIPGap if not model.IsMIP == 0 else 0.0,
        num_cont_vars=model.NumVars - model.NumBinVars,
        num_bin_vars=model.NumBinVars,
        dataset=scenario
    )

    return allocation


def calculate_nodal_ptdf(network):
    """
    Calculates the nodal PTDF matrix for the largest subnetwork in the given PyPSA network.
    Returns a DataFrame with lines as index and buses as columns, matching the full network.
    """
    network.determine_network_topology()
    sub_network_objects = network.sub_networks.obj

    if len(sub_network_objects) == 0:
        raise ValueError("No subnetworks found. The network might be empty or invalid.")
    elif len(sub_network_objects) > 1:
        print(f"Warning: Found {len(sub_network_objects)} electrical subnetworks. "
              "PTDF will be calculated for the largest one.")
        main_sub_network = max(sub_network_objects, key=lambda sn: len(sn.buses()))
    else:
        main_sub_network = sub_network_objects[0]

    print(f"Selected the main subnetwork with {len(main_sub_network.buses())} buses.")
    main_sub_network.calculate_PTDF()

    ptdf_numpy = main_sub_network.PTDF
    lines = main_sub_network.lines_i()
    buses = main_sub_network.buses_i()
    print(f"PTDF matrix shape: {ptdf_numpy.shape} (lines: {len(lines)}, buses: {len(buses)})")

    ptdf = pd.DataFrame(ptdf_numpy, index=lines, columns=buses)
    nodal_ptdf = pd.DataFrame(0.0, index=network.lines.index, columns=network.buses.index)
    nodal_ptdf.loc[lines, buses] = ptdf

    return nodal_ptdf


def fix_missing_generator_timeseries(network):
    """
    Fix missing generator time series data in the network by adding missing generators 
    with 100% availability.
    
    Args:
        network (pypsa.Network): PyPSA network object
        
    Returns:
        pypsa.Network: Network with fixed generator time series data
    """
    static_gens = network.generators.index
    timeseries_gens = network.generators_t.p_max_pu.columns
    missing_gens = static_gens.difference(timeseries_gens)

    if not missing_gens.empty:
        # Create availability profiles for missing generators (100% availability)
        new_series_list = [
            pd.Series(1.0, index=network.snapshots, name=gen_name)
            for gen_name in missing_gens
        ]
        
        # Add new profiles to the network
        network.generators_t.p_max_pu = pd.concat(
            [network.generators_t.p_max_pu] + new_series_list, 
            axis=1
        )
        
        # Verify the fix
        final_missing = network.generators.index.difference(
            network.generators_t.p_max_pu.columns
        )
        if not final_missing.empty:
            print("Warning: Some generators are still missing from time-series data")
            
    return network


def create_pypsa_network_from_scenario(scenario: Scenario) -> pypsa.Network:
    """
    Builds a PyPSA Network object from a Scenario object.

    :param scenario: The Scenario object containing network, buyer, and seller data.
    :return: A corresponding pypsa.Network object.
    """
    # 1. Initialize an empty PyPSA network
    n = pypsa.Network()
    n.name = scenario.name

    # 2. Set the time snapshots
    # Assuming periods are integer time steps, we can create a simple index.
    # If they represent actual times, pd.to_datetime could be used.
    snapshots = pd.Index(scenario.periods, name='snapshot')
    n.set_snapshots(snapshots)

    # 3. Add Buses (Nodes) with coordinates
    for node, data in scenario.nodes_agents.items():
        n.add("Bus",
              name=node,
              x=data['longitude'],
              y=data['latitude'])

    # 4. Add Transmission Lines (Edges)
    for i, (u, v, data) in enumerate(scenario.network.edges(data=True)):
        # Calculate reactance from susceptance (B). Assume resistance r=0 if not provided.
        reactance = 1 / data['B'] if data['B'] != 0 else 0
        
        n.add("Line",
              name=f"L_{i}",
              bus0=u,
              bus1=v,
              s_nom=data['F_max'],  # F_max maps to nominal power capacity
              x=reactance,          # PyPSA uses reactance 'x'
              r=0)                  # Assume resistance is zero

    # 5. Add Generators (from Sellers)
    # Get static attributes for each unique generator
    static_gen_data = scenario.df_sellers.drop_duplicates(subset='generator').set_index('generator')
    
    # Calculate nominal power (p_nom) as the maximum possible output across all periods
    p_nom = scenario.df_sellers.groupby('generator')['max_prod'].max()

    for gen_name, row in static_gen_data.iterrows():
        n.add("Generator",
              name=gen_name,
              bus=row['node'],
              carrier=row['carrier'],
              marginal_cost=row['cost1'],
              start_up_cost=row['no_load_cost'],
              p_nom=p_nom.get(gen_name, 0))
    
    # Add time-varying generator attributes (p_max_pu)
    if not n.generators.empty:
        p_max_pu_t = scenario.df_sellers.pivot(index='period', columns='generator', values='max_prod')
        # Normalize by p_nom to get per-unit values
        p_max_pu_t = p_max_pu_t / n.generators.p_nom
        n.generators_t.p_max_pu = p_max_pu_t.reindex(index=snapshots, columns=n.generators.index).fillna(0)

        p_min_pu_t = scenario.df_sellers.pivot(index='period', columns='generator', values='min_prod')
        p_min_pu_t = p_min_pu_t / n.generators.p_nom
        n.generators_t.p_min_pu = p_min_pu_t.reindex(index=snapshots, columns=n.generators.index).fillna(0)


    # 6. Add Loads (from Buyers)
    # PyPSA typically has one load per bus. We'll aggregate buyers by bus if necessary.
    # The provided data has one buyer per node, which simplifies this.
    bus_demand = scenario.df_buyers.groupby(['period', 'node'])['max_dem'].sum().unstack(level='node')
    bus_demand = bus_demand.reindex(index=snapshots, columns=n.buses.index).fillna(0)

    # Add Load components
    for bus_name in bus_demand.columns:
        if bus_demand[bus_name].sum() > 0: # Only add loads where there is demand
            n.add("Load",
                  name=bus_name, # Name the load after its bus for simplicity
                  bus=bus_name)
    
    # Attach the time-series demand data
    n.loads_t.p_set = bus_demand.rename_axis(None, axis=1)

    return n