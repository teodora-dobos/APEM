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


class Zonal_NTC_multiedge(PowerFlowModel):
    """
    Variant of the zonal NTC model that preserves individual cross‑zonal lines
    (no aggregation). Each interzonal line in the nodal network becomes its own
    edge in a zonal ``MultiGraph`` so parallel connections are modeled
    independently. Works only with PyPSA data.
    """

    def __init__(self, zonal_configuration: str = 'zonal_DE3', factor: float = 0.8):
        self.zonal_configuration = zonal_configuration
        self.factor = factor

    def create_zonal_scenario_NTC(self, base_scenario: Scenario) -> Scenario:
        """
        Convert a nodal scenario into a zonal one while keeping every
        cross‑zonal line as a separate edge.
        """
        # Work on copies to avoid mutating the input nodal scenario in place.
        df_sellers = base_scenario.df_sellers.copy()
        df_buyers = base_scenario.df_buyers.copy()

        node_to_zone, zones = {}, {}

        for node in base_scenario.network.nodes:
            if node not in base_scenario.nodes_agents:
                continue  # skip nodes without coordinate information

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

        if not zones:
            raise ValueError(
                f"{self}: no nodes could be mapped to zones for zonal_configuration={self.zonal_configuration}. "
                "Ensure nodes_agents includes latitude/longitude for network nodes."
            )

        # save node_to_zone assignment as .csv file (include factor for consistency with result paths)
        factor_str = f"_f{self.factor}" if self.factor is not None else ""
        results_path = f"US_results/{base_scenario.name}_results/Zonal_NTC_multiedge/{self.zonal_configuration}{factor_str}"
        os.makedirs(results_path, exist_ok=True)
        node_to_zone_df = pd.DataFrame(list(node_to_zone.items()), columns=['node', 'zone'])
        node_to_zone_df.to_csv(os.path.join(results_path, "node_to_zone.csv"), index=False)

        # create network that keeps every cross‑zonal line as an individual edge
        aggregated_network = nx.MultiGraph()

        for z in zones:
            aggregated_network.add_node(z)

        is_multi = base_scenario.network.is_multigraph()
        edge_iter = base_scenario.network.edges(keys=True, data=True) if is_multi else base_scenario.network.edges(data=True)

        for edge in edge_iter:
            if is_multi:
                v, w, _k, data = edge
            else:
                v, w, data = edge

            if v not in node_to_zone or w not in node_to_zone:
                continue

            zone_v = node_to_zone[v]
            zone_w = node_to_zone[w]

            # keep only inter‑zonal lines; intra‑zonal lines vanish in zonal model
            if zone_v == zone_w:
                continue

            aggregated_network.add_edge(
                zone_v,
                zone_w,
                B=data['B'],
                F_max=data['F_max'] * self.factor
            )

        # if only a single zone exists: create network without edges
        if len(aggregated_network.nodes) == 1:
            aggregated_network = nx.Graph()
            aggregated_network.add_node(next(iter(zones.keys())))

        r_star = list(aggregated_network.nodes)[0]

        # for each zone, we store its sellers and buyers
        nodes_agents = {}
        for z in zones:
            nodes_agents[z] = {}
            nodes_agents[z]['sellers'] = df_sellers[df_sellers['node'] == z]['seller'].unique().tolist()
            nodes_agents[z]['buyers'] = df_buyers[df_buyers['node'] == z]['buyer'].unique().tolist()
            # keep representative coordinates for plotting
            rep_node = zones[z]
            rep_coords = base_scenario.nodes_agents.get(rep_node, {})
            if rep_coords:
                nodes_agents[z]['latitude'] = rep_coords.get('latitude')
                nodes_agents[z]['longitude'] = rep_coords.get('longitude')

        return Scenario(f'{base_scenario.name}', df_buyers, df_sellers, aggregated_network, nodes_agents,
                        base_scenario.periods, base_scenario.blocks_buyers, base_scenario.blocks_sellers, r_star)

    def solve(self, scenario: Scenario, configuration: Configuration, results_file: Optional[str] = None,
              stats_file: Optional[str] = None, u_fixed: Optional[dict] = None) \
            -> Tuple[Scenario, Union[Allocation, Error]]:
        # create a zonal NTC scenario with explicit lines
        zonal_scenario = self.create_zonal_scenario_NTC(base_scenario=scenario)

        # solve a DCOPF problem for the constructed zonal network
        dcopf = DCOPF()
        return zonal_scenario, dcopf.solve(zonal_scenario, configuration, results_file, stats_file)

    def __str__(self):
        return 'Zonal_NTC_multiedge'


# Backward compatibility alias
Zonal_NTC_independent = Zonal_NTC_multiedge
