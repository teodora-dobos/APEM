from itertools import combinations
import os.path
from typing import Optional, Tuple, Union

import networkx as nx
import pandas as pd

from apem.US_market_model.allocation.algorithms.nodal_clearing.dcopf import DCOPF
from apem.US_market_model.allocation.allocation import Allocation
from apem.US_market_model.allocation.configuration import Configuration
from apem.US_market_model.allocation.error import Error
from apem.US_market_model.allocation.power_flow_model import PowerFlowModel
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_configuration import node_zone_mapper
from apem.US_market_model.data.parsing.scenario import Scenario


class Zonal_NTC_aggregated(PowerFlowModel):
    """
    Implementation of the Zonal NTC model. A zonal NTC model includes a simple graph with at most one line
    between any two nodes, where the nodes represent the zones. 
    Note: Works only with PyPSA data.
    """

    def __init__(self, zonal_configuration: str = 'zonal_DE3', factor: float = 0.8):
        self.zonal_configuration = zonal_configuration
        self.factor = factor

    def create_zonal_scenario_NTC(self, base_scenario: Scenario) -> Scenario:
        """
        Construct a zonal scenario based on a given nodal base scenario.
        """
        df_sellers = base_scenario.df_sellers
        df_buyers = base_scenario.df_buyers

        node_to_zone, zones = {}, {}
        
        for node in base_scenario.network.nodes:
            if node not in base_scenario.nodes_agents:
                continue # skip nodes without coordinate information
            
            lat = base_scenario.nodes_agents[node]["latitude"]
            lon = base_scenario.nodes_agents[node]["longitude"]
            
            # map node to zone based on latitude and longitude coordinates
            zone = node_zone_mapper(self.zonal_configuration, lat=lat, lon=lon)
            node_to_zone[node] = zone
            
            # ensure each zone is represented by a single node within that zone
            zones.setdefault(zone, node)
            
            # the sellers and buyers at the current node are assigned to the zone
            df_sellers.loc[df_sellers['node'] == node, 'node'] = zone
            df_buyers.loc[df_buyers['node'] == node, 'node'] = zone

        # save node_to_zone assignment as .csv file (include factor for consistency with result paths)
        factor_str = f"_f{self.factor}" if self.factor is not None else ""
        results_path = f"US_results/{base_scenario.name}_results/Zonal_NTC_aggregated/{self.zonal_configuration}{factor_str}"
        os.makedirs(results_path, exist_ok=True)
        node_to_zone_df = pd.DataFrame(list(node_to_zone.items()), columns=['node', 'zone'])
        node_to_zone_df.to_csv(os.path.join(results_path, "node_to_zone.csv"), index=False)

        # create network with one line between any two zones
        aggregated_network = nx.Graph()
        if len(zones) > 1:
            lines = {(z1, z2): {'F_max': 0, 'B': float('inf')} for z1, z2 in combinations(sorted(zones), 2)}

            # for each interconnector between two zones set
            # its capacity to the sum of the capacities of the cross-zonal lines multiplied by self.factor and
            # its susceptance to the minimum susceptance of any cross-zonal line
            for v, w, data in base_scenario.network.edges(data=True):
                # skip lines touching nodes without zone assignment (e.g., missing coordinates)
                if v not in node_to_zone or w not in node_to_zone:
                    continue

                zone_v = node_to_zone[v]
                zone_w = node_to_zone[w]

                # intra-zonal lines are not represented in the zonal network
                if zone_v == zone_w:
                    continue

                z1, z2 = sorted((zone_v, zone_w))
                lines[z1, z2]['F_max'] += data['F_max']
                lines[z1, z2]['B'] = min(lines[z1, z2]['B'], data['B'])

            # add edges to the aggregated network, only if B no longer is set to inf (i.e., if at least one line between
            # the zones existed in the base scenario)
            for z1, z2 in combinations(sorted(zones), 2):
                if lines[z1, z2]['B'] != float('inf'):
                    aggregated_network.add_edge(
                        z1, z2,
                        B=lines[z1, z2]['B'],
                        F_max=lines[z1, z2]['F_max'] * self.factor
                    )
         
        # if only a single zone exists: create network without edges  
        else:
            national_zone = list(zones.keys())[0]
            aggregated_network.add_node(national_zone)

        r_star = list(aggregated_network.nodes)[0]

        # for each zone, we store its sellers and buyers
        nodes_agents = {}
        for z in zones:
            nodes_agents[z] = {}
            nodes_agents[z]['sellers'] = df_sellers[df_sellers['node'] == z]['seller'].unique().tolist()
            nodes_agents[z]['buyers'] = df_buyers[df_buyers['node'] == z]['buyer'].unique().tolist()

        return Scenario(f'{base_scenario.name}', df_buyers, df_sellers, aggregated_network, nodes_agents,
                        base_scenario.periods, base_scenario.blocks_buyers, base_scenario.blocks_sellers, r_star)

    def solve(self, scenario: Scenario, configuration: Configuration, results_file: Optional[str] = None,
              stats_file: Optional[str] = None, u_fixed: Optional[dict] = None) \
            -> Tuple[Scenario, Union[Allocation, Error]]:
        # create a zonal NTC scenario
        zonal_scenario = self.create_zonal_scenario_NTC(base_scenario=scenario)

        # solve a DCOPF problem for the constructed zonal network
        dcopf = DCOPF()
        return zonal_scenario, dcopf.solve(zonal_scenario, configuration, results_file, stats_file)

    def __str__(self):
        return 'Zonal_NTC_aggregated'


# Backward compatibility alias
Zonal_NTC = Zonal_NTC_aggregated
