import pandas as pd
import pypsa
from apem.unit_based_model.data.parsing.scenario import Scenario


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
        main_sub_network = sub_network_objects.iloc[0]

    main_sub_network.calculate_PTDF()

    ptdf_numpy = main_sub_network.PTDF
    lines = main_sub_network.lines_i()
    buses = main_sub_network.buses_i()

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


def _get_node_coords(nodes_agents: dict) -> dict:
    """
    Return a mapping node -> (lon, lat). If coordinates are missing, generate synthetic
    ones along a line to avoid hard dependency on geodata.
    """
    coords = {}
    missing = []
    for node, data in nodes_agents.items():
        lon = data.get("longitude")
        lat = data.get("latitude")
        if lon is None or lat is None:
            missing.append(node)
        else:
            coords[node] = (lon, lat)

    if missing:
        # simple deterministic layout along x-axis for missing coords
        for idx, node in enumerate(missing):
            coords[node] = (float(idx), 0.0)
        print(
            f"Warning: missing latitude/longitude for {len(missing)} node(s); using synthetic coordinates. "
            "Results are still computed, but geographic plots may be meaningless."
        )
    return coords


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
    snapshots = pd.Index(scenario.periods, name='snapshot')
    n.set_snapshots(snapshots)

    # 3. Add Buses (Nodes) with coordinates (real or synthetic)
    node_coords = _get_node_coords(scenario.nodes_agents)
    for node, (lon, lat) in node_coords.items():
        n.add("Bus", name=node, x=lon, y=lat)

    # 4. Add Transmission Lines (Edges)
    for i, (u, v, data) in enumerate(scenario.network.edges(data=True)):
        # Calculate reactance from susceptance (B). Assume resistance r=0 if not provided.
        reactance = 1 / data['B'] if data['B'] != 0 else 0

        n.add("Line",
              name=f"L_{i}",
              bus0=u,
              bus1=v,
              s_nom=data['F_max'],  # F_max maps to nominal power capacity
              x=reactance,  # PyPSA uses reactance 'x'
              r=0)  # Assume resistance is zero

    # 5. Add Generators (from Sellers)
    generator_col = "generator" if "generator" in scenario.df_sellers.columns else "seller"

    # Get static attributes for each unique generator
    static_gen_data = scenario.df_sellers.drop_duplicates(subset=generator_col).set_index(generator_col)

    # Calculate nominal power (p_nom) as the maximum possible output across all periods
    p_nom = scenario.df_sellers.groupby(generator_col)["max_prod"].max()

    for gen_name, row in static_gen_data.iterrows():
        n.add(
            "Generator",
            name=gen_name,
            bus=row["node"],
            carrier=row.get("carrier", "unknown"),
            marginal_cost=row.get("cost1", 0),
            start_up_cost=row.get("no_load_cost", 0),
            p_nom=p_nom.get(gen_name, 0),
        )

    # Add time-varying generator attributes (p_max_pu)
    if not n.generators.empty:
        p_max_pu_t = scenario.df_sellers.pivot(index="period", columns=generator_col, values="max_prod")
        # Normalize by p_nom to get per-unit values
        p_max_pu_t = p_max_pu_t / n.generators.p_nom
        n.generators_t.p_max_pu = p_max_pu_t.reindex(index=snapshots, columns=n.generators.index).fillna(0)

        p_min_pu_t = scenario.df_sellers.pivot(index="period", columns=generator_col, values="min_prod")
        p_min_pu_t = p_min_pu_t / n.generators.p_nom
        n.generators_t.p_min_pu = p_min_pu_t.reindex(index=snapshots, columns=n.generators.index).fillna(0)

    # 6. Add Loads (from Buyers)
    # PyPSA typically has one load per bus. We'll aggregate buyers by bus if necessary.
    # The provided data has one buyer per node, which simplifies this.
    if scenario.df_buyers.empty:
        bus_demand = pd.DataFrame(index=snapshots)
    else:
        bus_demand = scenario.df_buyers.groupby(["period", "node"])["max_dem"].sum().unstack(level="node")
        bus_demand = bus_demand.reindex(index=snapshots, columns=n.buses.index).fillna(0)

    # Add Load components
    for bus_name in bus_demand.columns:
        if bus_demand[bus_name].sum() > 0:  # Only add loads where there is demand
            n.add("Load", name=bus_name, bus=bus_name)

    # Attach the time-series demand data
    if not bus_demand.empty:
        n.loads_t.p_set = bus_demand.rename_axis(None, axis=1)

    return n

