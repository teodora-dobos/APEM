import pypsa
import pandas as pd
from gurobipy import GRB
import logging
from typing import Optional, Union
import os
import networkx as nx
from itertools import combinations

from apem.US_market_model.allocation.power_flow_model import PowerFlowModel
from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.allocation.configuration import Configuration
from apem.US_market_model.allocation.allocation import Allocation
from apem.US_market_model.allocation.error import Error
from apem.US_market_model.allocation.analysis.stats import compute_stats
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_configuration import node_zone_mapper

from apem.US_market_model.allocation.algorithms.fbmc_utils import (
    create_pypsa_network_from_scenario,
    fix_missing_generator_timeseries,
    calculate_nodal_ptdf,
)

from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_fbmc import (
    BaseCaseGenerator,
    ZonalDispatchModel,
    get_zone_maps,
    aggregate_by_zone,
)


class ZonalFBMC(PowerFlowModel):
    """
    Implementation of the Zonal Flow-Based Market Coupling Model.
    
    This class wraps the ZonalDispatchModel to work within the APEM framework,
    handling the full workflow from scenario parsing to returning an Allocation object.
    Redispatch is currently ignored.
    """

    def __init__(self, zonal_configuration: str, base_case_type: str = 'BC2'):
        """
        Initializes the ZonalFBMC model.
        :param zonal_configuration: The name of the zonal configuration to use (e.g., 'zonal_DE4-refined').
        :param base_case_type: The type of base case to generate (e.g., 'BC1', 'BC4').
        """
        self.zonal_configuration = zonal_configuration
        self.node_zone_mapper = node_zone_mapper
        self.base_case_type = base_case_type
        super().__init__()

    def create_zonal_scenario_FBMC(self, base_scenario: Scenario) -> Scenario:
        """
        Create a zonal scenario from the base nodal scenario.
        
        This creates a simplified zonal representation that can be used for DCOPF
        and integrates with the existing redispatch framework.
        
        Args:
            base_scenario: The original nodal scenario
            
        Returns:
            Scenario: A zonal scenario suitable for DCOPF solving
        """

        # Convert to PyPSA network to get zone mappings
        network = create_pypsa_network_from_scenario(base_scenario)
        network = fix_missing_generator_timeseries(network)

        # Get zone mappings
        node_to_zone, zone_to_nodes = get_zone_maps(
            network, node_zone_mapper, self.zonal_configuration
        )

        # Create aggregated zonal data
        df_sellers = base_scenario.df_sellers.copy()
        df_buyers = base_scenario.df_buyers.copy()

        # Map nodes to zones in seller and buyer data
        for node, zone in node_to_zone.items():
            df_sellers.loc[df_sellers['node'] == node, 'node'] = str(zone)
            df_buyers.loc[df_buyers['node'] == node, 'node'] = str(zone)

        # Aggregate by zone and keep the scenario structure
        # For sellers: aggregate by zone but maintain unique seller IDs
        for zone_id, nodes_in_zone in zone_to_nodes.items():
            zone_str = str(zone_id)
            # Update all sellers in this zone to use the zone as their node
            df_sellers.loc[df_sellers['node'].isin(nodes_in_zone), 'node'] = zone_str
            df_buyers.loc[df_buyers['node'].isin(nodes_in_zone), 'node'] = zone_str

        # Create simplified zonal network with Flow-Based constraints
        aggregated_network = nx.Graph()
        zones = list(zone_to_nodes.keys())

        if len(zones) > 1:
            # Create zonal network - for FBMC we create a more connected structure
            # Add all zones as nodes
            for zone in zones:
                aggregated_network.add_node(str(zone))

            # Calculate zonal transmission capacities based on Flow-Based domain
            # For now, create connections between all zone pairs
            for z1, z2 in combinations(zones, 2):
                # Calculate aggregate capacity between zones
                total_capacity = 0
                min_susceptance = float('inf')

                # Sum capacities of all lines connecting the two zones
                for node1 in zone_to_nodes[z1]:
                    for node2 in zone_to_nodes[z2]:
                        if base_scenario.network.has_edge(node1, node2):
                            edge_data = base_scenario.network[node1][node2]
                            total_capacity += edge_data.get('F_max', 0)
                            min_susceptance = min(min_susceptance, edge_data.get('B', float('inf')))

                # Add zonal connection if there are physical connections
                if total_capacity > 0 and min_susceptance != float('inf'):
                    aggregated_network.add_edge(
                        str(z1), str(z2),
                        F_max=total_capacity * 0.8,  # Apply capacity factor
                        B=min_susceptance
                    )
        else:
            # Single zone case
            aggregated_network.add_node(str(zones[0]))

        # Create nodes_agents for zones
        nodes_agents = {}
        for zone_id, nodes_in_zone in zone_to_nodes.items():
            zone_str = str(zone_id)
            nodes_agents[zone_str] = {
                'sellers': df_sellers[df_sellers['node'] == zone_str]['seller'].unique().tolist(),
                'buyers': df_buyers[df_buyers['node'] == zone_str]['buyer'].unique().tolist(),
                'latitude': network.buses.loc[nodes_in_zone[0], 'y'],  # Use first node's coordinates
                'longitude': network.buses.loc[nodes_in_zone[0], 'x']
            }

        # Save zone mappings for later use
        results_path = f"US_results/{base_scenario.name}_results/Zonal_FBMC/{self.zonal_configuration}"
        os.makedirs(results_path, exist_ok=True)
        node_to_zone_df = pd.DataFrame(list(node_to_zone.items()), columns=['node', 'zone'])
        node_to_zone_df.to_csv(os.path.join(results_path, "node_to_zone.csv"), index=False)

        # Reference zone (first zone)
        r_star = str(list(zone_to_nodes.keys())[0])

        # Return a zonal scenario
        return Scenario(
            name=f'{base_scenario.name}',
            df_buyers=df_buyers,
            df_sellers=df_sellers,
            network=aggregated_network,
            nodes_agents=nodes_agents,
            periods=base_scenario.periods,
            blocks_buyers=base_scenario.blocks_buyers,
            blocks_sellers=base_scenario.blocks_sellers,
            r_star=r_star
        )

    def solve(self, scenario: Scenario, configuration: Configuration, results_file: Optional[str] = None,
              stats_file: Optional[str] = None, u_fixed: Optional[dict] = None, redispatch: Optional[bool] = False,
              min_cost: Optional[bool] = False, min_vol: Optional[bool] = False,
              zonal_allocation: Optional[Allocation] = None) -> Union[Allocation, Error]:
        """
        Formulates and solves the Zonal FBMC problem.
        """

        try:
            zonal_scenario = self.create_zonal_scenario_FBMC(scenario)
            # 1. Convert Scenario to PyPSA Network and calculate PTDF
            network = create_pypsa_network_from_scenario(scenario)
            network = fix_missing_generator_timeseries(network)
            nodal_ptdf = calculate_nodal_ptdf(network=network)

            # 2. Generate the Base Case for the Zonal Model
            base_case_gen = BaseCaseGenerator(network, nodal_ptdf, self.node_zone_mapper, self.zonal_configuration)
            p_bus_expected = base_case_gen.generate(self.base_case_type)

            if p_bus_expected is None:
                print(f'{self} allocation error: Base case generation failed.')
                return Error(-2)  # Specific error for base case failure

            # 3. Solve the Zonal Dispatch Model
            zonal_model = ZonalDispatchModel()
            zonal_results = zonal_model.solve(
                network=network,
                nodal_ptdf=nodal_ptdf,
                p_bus_expected=p_bus_expected,
                node_zone_mapper=self.node_zone_mapper,
                zonal_configuration=self.zonal_configuration,
                verbose=False,
                configuration=configuration
            )

            if zonal_results is None:
                print(f'{self} allocation error: ZonalDispatchModel failed to solve.')
                return Error(-1)

            # 4. Convert results to Allocation object
            allocation = create_allocation_from_zonal_results(zonal_results, network, zonal_scenario, self,
                                                              p_bus_expected, nodal_ptdf)

            if stats_file and zonal_results.get('model'):
                os.makedirs(os.path.dirname(stats_file), exist_ok=True)
                compute_stats(stats_file, scenario, configuration, allocation, zonal_results['model'])

            if results_file:
                os.makedirs(os.path.dirname(results_file), exist_ok=True)
                self._save_zonal_results(zonal_results, results_file)

            return zonal_scenario, allocation

        except Exception as e:
            logging.exception("An error occurred during ZonalFBMC solve.")
            print(f'{self} allocation error: {str(e)}')
            return Error(-1)

    def _save_zonal_results(self, zonal_results, results_file):
        """
        Save zonal FBMC specific results to files.
        """

        try:
            model = zonal_results.get('model')
            if model is None:
                print("Could not save results: model object not found in results.")
                return

            status = model.Status
            if status == GRB.OPTIMAL:
                # Use the pre-extracted list of variables
                results_data = zonal_results.get("all_vars")
                if results_data is None:
                    print("Could not save results: 'all_vars' key not found in results dictionary.")
                    return

                df = pd.DataFrame(results_data, columns=["variable", "value"])
                df.to_csv(results_file, index=False)
                print(f"Successfully saved {len(results_data)} variables to {results_file}")

            else:
                # This logic for non-optimal cases remains the same
                status_message = {
                    GRB.INF_OR_UNBD: "Model is infeasible or unbounded",
                    GRB.INFEASIBLE: "Model is infeasible",
                    GRB.UNBOUNDED: "Model is unbounded",
                    GRB.INTERRUPTED: "Optimization was interrupted",
                }.get(status, f"Optimization failed with unknown status code: {status}")

                print(f"Could not save results: {status_message}")
                error_data = [{"status": status, "message": status_message}]
                df = pd.DataFrame(error_data, columns=["status", "message"])
                df.to_csv(results_file, index=False)

        except Exception as e:
            print(f"An unexpected error occurred in _save_results_to_file: {e}")

    def __str__(self):
        return f'Zonal_FBMC'


def create_allocation_from_zonal_results(zonal_results: dict, network: pypsa.Network,
                                         zonal_scenario: Scenario, power_flow_model: 'ZonalFBMC',
                                         p_bus_expected: pd.DataFrame, nodal_ptdf: pd.DataFrame) -> Allocation:
    """
    Creates a purely ZONAL allocation object that matches the zonal_scenario.
    It synthesizes inter-zonal flows by aggregating the nodal flows from the Base Case.
    """
    model = zonal_results.get('model')
    if model is None or model.Status != GRB.OPTIMAL:
        raise ValueError("Cannot create allocation from a non-optimally solved or missing model.")

    # --- 1. Extract raw results and create helper mappings ---
    p_gen_df = zonal_results['p_gen']
    u_df = zonal_results['u']
    nse_tz_df = zonal_results['nse_tz']
    zonal_prices_df = zonal_results['duals']['zonal_price']
    startup_df = (u_df.diff().fillna(u_df.iloc[0])).clip(lower=0)

    periods = zonal_scenario.periods
    snapshot_to_period = {snap: p for p, snap in zip(periods, network.snapshots)}
    node_to_zone, _ = get_zone_maps(network, power_flow_model.node_zone_mapper, power_flow_model.zonal_configuration)

    # --- 2. Synthesize Zonal f_vwt from Base Case Nodal Flows ---
    nodal_flow_df = nodal_ptdf.dot(p_bus_expected.T).T
    f_vwt = {}

    # Initialize all edges in the zonal network with zero flow
    for t in periods:
        for v, w in zonal_scenario.network.edges():
            f_vwt[(v, w, t)] = 0.0
            f_vwt[(w, v, t)] = 0.0

    # Aggregate nodal flows onto the zonal interconnectors
    for line_name, flows_over_time in nodal_flow_df.items():
        if line_name in network.lines.index:
            line_info = network.lines.loc[line_name]
            node_v, node_w = line_info.bus0, line_info.bus1

            zone_v = str(node_to_zone.get(node_v))
            zone_w = str(node_to_zone.get(node_w))

            if zone_v != zone_w:
                for snapshot, flow in flows_over_time.items():
                    t = snapshot_to_period[snapshot]
                    # Add flow to the corresponding zonal interconnector
                    if (zone_v, zone_w, t) in f_vwt:
                        f_vwt[(zone_v, zone_w, t)] += flow
                        f_vwt[(zone_w, zone_v, t)] -= flow
                    # Handle cases where the edge might be defined in reverse
                    elif (zone_w, zone_v, t) in f_vwt:
                        f_vwt[(zone_w, zone_v, t)] += flow
                        f_vwt[(zone_v, zone_w, t)] -= flow

    # --- 3. Populate other Zonal Allocation Dictionaries ---

    # alpha_vt (Zonal Prices)
    alpha_vt = {}
    for zone_id, price_series in zonal_prices_df.items():
        zone_str = str(zone_id)
        for snapshot, price in price_series.items():
            alpha_vt[(zone_str, snapshot_to_period[snapshot])] = price

    # No slack variables in zonal FBMC; default to zero slack
    slack_vt = {(v, t): 0.0 for v in zonal_scenario.network.nodes for t in periods}

    # Seller data (y_st, u_st, phi_st) - no aggregation needed
    y_st, u_st, phi_st = {}, {}, {}
    gen_name_to_seller_id = pd.Series(zonal_scenario.df_sellers.seller.values,
                                      index=zonal_scenario.df_sellers.generator).to_dict()
    for gen_name in p_gen_df.columns:
        seller_id = gen_name_to_seller_id.get(gen_name)
        if seller_id is None: continue
        for snapshot, val in p_gen_df[gen_name].items():
            period = snapshot_to_period[snapshot]
            y_st[(seller_id, period)] = val
            u_st[(seller_id, period)] = round(u_df.loc[snapshot, gen_name])
            phi_st[(seller_id, period)] = startup_df.loc[snapshot, gen_name]
    y_stl = {(s, t, 1): val for (s, t), val in y_st.items()}

    # Buyer data (x_bt, x_btl) - needs zonal aggregation
    x_bt, x_btl = {}, {}
    bus_demand_df = network.loads_t.p_set.T.groupby(network.loads.bus).sum().T
    zonal_demand_df = aggregate_by_zone(bus_demand_df, node_to_zone)
    for zone_id, nse_series in nse_tz_df.items():
        zone_str = str(zone_id)
        for snapshot, nse_val in nse_series.items():
            period = snapshot_to_period[snapshot]
            total_zonal_demand = zonal_demand_df.loc[snapshot, zone_id]
            served_ratio = 1.0 - (nse_val / total_zonal_demand) if total_zonal_demand > 1e-6 else 1.0

            buyers_in_zone = zonal_scenario.nodes_agents.get(zone_str, {}).get('buyers', [])
            for b in buyers_in_zone:
                buyer_info = zonal_scenario.df_buyers[
                    (zonal_scenario.df_buyers['buyer'] == b) & (zonal_scenario.df_buyers['period'] == period)
                    ].iloc[0]

                # Calculate total accepted demand
                original_demand = buyer_info['inelastic_dem'] + sum(
                    buyer_info[f'size_{lb}'] for lb in zonal_scenario.blocks_buyers)
                accepted_demand = original_demand * served_ratio
                x_bt[(b, period)] = accepted_demand

                # Reconstruct block-level acceptance (x_btl)
                remaining_demand_to_fulfill = accepted_demand

                # Inelastic demand is always met first
                inelastic_accepted = min(remaining_demand_to_fulfill, buyer_info['inelastic_dem'])
                remaining_demand_to_fulfill -= inelastic_accepted

                # Iterate through elastic blocks
                for lb in zonal_scenario.blocks_buyers:
                    block_size = buyer_info[f'size_{lb}']
                    accepted_for_block = min(remaining_demand_to_fulfill, block_size)
                    x_btl[(b, period, lb)] = accepted_for_block
                    remaining_demand_to_fulfill -= accepted_for_block

    # --- 4. Instantiate and return the final ZONAL Allocation ---
    return Allocation(
        welfare=model.ObjVal,
        x_bt=x_bt,
        y_st=y_st,
        x_btl=x_btl,  # Simplified for zonal model
        y_stl=y_stl,
        f_vwt=f_vwt,
        alpha_vt=alpha_vt,
        u_st=u_st,
        phi_st=phi_st,
        slack_vt=slack_vt,
        power_flow_model=power_flow_model,
        runtime=model.Runtime,
        num_vars=model.NumVars,
        num_constrs=model.NumConstrs,
        MIP_gap=model.MIPGap if not model.IsMIP == 0 else 0.0,
        num_cont_vars=model.NumVars - model.NumBinVars,
        num_bin_vars=model.NumBinVars,
        dataset=zonal_scenario
    )
