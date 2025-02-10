from itertools import combinations
import os.path
from typing import Optional, Tuple, Union

import networkx as nx
import pandas as pd
import pypsa

from src.allocation.algorithms.dcopf import DCOPF
from src.allocation.allocation import Allocation
from src.allocation.configuration import Configuration
from src.allocation.error import Error
from src.allocation.power_flow_model import PowerFlowModel
from src.allocation.zonal_configuration import node_zone_mapper
from src.data.parsing.scenario import Scenario


class Zonal_NTC(PowerFlowModel):
    """
    Implementation of the Zonal NTC model. A zonal NTC model includes a simple graph with at most one line
    between any two nodes, where the nodes represent the zones. 
    Note: Works only with PyPSA data.
    """

    def __init__(self, zonal_configuration: str, factor: float = 0.8):
        self.zonal_configuration = zonal_configuration
        self.factor = factor


    def create_zonal_scenario_NTC(self, base_scenario: Scenario, network: pypsa.Network) -> Scenario:
        """
        Construct a zonal scenario based on a given nodal base scenario.
        """
        df_sellers = base_scenario.df_sellers
        df_buyers = base_scenario.df_buyers

        node_to_zone, zones = {}, {}
        for node in base_scenario.network.nodes:
            for node_index in list(network.buses.index):
                if str(node) == node_index:
                    lon = network.buses[network.buses.index == node_index]['x'][0]
                    lat = network.buses[network.buses.index == node_index]['y'][0]

                    # map node to zone based on latitude and longitude coordinates
                    zone = node_zone_mapper(self.zonal_configuration, lat=lat, lon=lon)
                    node_to_zone[node] = zone

                    # each zone is represented by a single node within that zone
                    zones.setdefault(zone, node)

                    # the sellers and buyers at the current node are assigned to the zone
                    df_sellers.loc[df_sellers['node'] == node, 'node'] = zone
                    df_buyers.loc[df_buyers['node'] == node, 'node'] = zone

                    break
                
        # save node_to_zone assignment as .csv file
        results_path = f"results/{base_scenario.name}_results/Zonal_NTC/{self.zonal_configuration}"
        os.makedirs(results_path, exist_ok=True)
        node_to_zone_df = pd.DataFrame(list(node_to_zone.items()), columns=['node', 'zone'])
        node_to_zone_df.to_csv(os.path.join(results_path, "node_to_zone.csv"), index=False)

        # create network with one line between any two zones
        aggregated_network = nx.Graph()
        lines = {(z1, z2): {'F_max': 0, 'B': float('inf')} for z1, z2 in combinations(sorted(zones), 2)}

        # for each interconnector between two zones set
        # its capacity to the sum of the capacities of the cross-zonal lines multiplied by self.factor and
        # its susceptance to the minimum susceptance of any cross-zonal line
        for v in base_scenario.network.nodes:
            for w in base_scenario.network.nodes:
                if node_to_zone[v] < node_to_zone[w] and (v, w) in base_scenario.network.edges():
                    lines[node_to_zone[v], node_to_zone[w]]['F_max'] += base_scenario.network[v][w]['F_max']
                    lines[node_to_zone[v], node_to_zone[w]]['B'] = min(lines[node_to_zone[v], node_to_zone[w]]['B'],
                                                                       base_scenario.network[v][w]['B'])
        
        # Add edges to the aggregated network, only if B no longer is set to inf (i.e., if at least one line between the zones existed in the base scenario)
        for z1, z2 in combinations(sorted(zones), 2):
            if lines[z1, z2]['B'] != float('inf'):
                aggregated_network.add_edge(
                    z1, z2,
                    B=lines[z1, z2]['B'],
                    F_max=lines[z1, z2]['F_max'] * self.factor
                )

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

        # load the PyPSA network
        if scenario.name == 'PyPSA_Eur_Large':
            n = pypsa.Network("src/data/raw_data/pypsa_eur_large/elec_s_334m_ec_lv1.5_.nc")
        elif scenario.name == 'PyPSA_Eur_Small':
            n = pypsa.Network("src/data/raw_data/pypsa_eur_small/elec_s_40_ec_lv1.5_.nc")

        # create a zonal NTC scenario
        zonal_scenario = self.create_zonal_scenario_NTC(base_scenario=scenario, network=n)

        # solve a DCOPF problem for the constructed zonal network
        dcopf = DCOPF()
        return zonal_scenario, dcopf.solve(zonal_scenario, configuration, results_file)


    def __str__(self):
        return 'Zonal_NTC'
