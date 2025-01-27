from typing import Union, Optional

import networkx as nx
import pandas as pd
import pypsa
from matplotlib import pyplot as plt


class Scenario:
    """
    Buyers, sellers and network data.
    """

    def __init__(self, name: str, df_buyers: pd.DataFrame, df_sellers: pd.DataFrame, network: nx.Graph,
                 nodes_agents: dict, periods: list, blocks_buyers: range, blocks_sellers: range,
                 r_star: Union[str, int], network_file: Optional[str] = None):
        self.name = name
        self.df_buyers = df_buyers
        self.df_sellers = df_sellers
        self.network = network
        self.nodes_agents = nodes_agents
        self.periods = periods
        self.blocks_buyers = blocks_buyers
        self.blocks_sellers = blocks_sellers
        self.r_star = r_star
        self.network_file = network_file

    def __str__(self):
        return self.name

    def analyze_scenario(self, output_file: str) -> None:
        """
        Computes statistics.
        """
        count_sellers = len(self.df_sellers['seller'].unique())
        count_buyers = len(self.df_buyers['buyer'].unique())
        count_nodes = len(self.df_sellers['node'].unique())

        energy_carriers = self.df_sellers['carrier'].unique().tolist()

        res_carriers = ['onwind', 'solar', 'offwind-ac', 'offwind-dc']
        res_sellers = self.df_sellers[self.df_sellers['carrier'].isin(res_carriers)]
        res_proportion = round(len(res_sellers) / len(self.df_sellers), 2)
        demand = self.df_buyers['max_dem'].sum()
        supply = self.df_sellers['max_prod'].sum()

        f = open(output_file, 'w+')
        f.write(f'Sellers: {count_sellers}\n')
        f.write(f'Buyers: {count_buyers}\n')
        f.write(f'Nodes: {count_nodes}\n')
        f.write(f'Transmission lines: {len(self.network)}\n')
        f.write(f'Periods: {len(self.periods)}\n')
        f.write(f'Energy carriers: {energy_carriers}\n')
        f.write(f'RES proportion in energy mix: {res_proportion}\n')
        f.write(f'Demand: {demand}\n\n')

        for t in self.periods:
            demand_t = self.df_buyers[self.df_buyers['period'] == t]['max_dem'].sum()
            f.write(f'Demand period {t}: {demand_t}\n')

        f.write('\n')
        f.write(f'Available supply: {supply}\n\n')
        for t in self.periods:
            supply_t = self.df_sellers[self.df_sellers['period'] == t]['max_prod'].sum()
            f.write(f'Available supply period {t}: {supply_t}\n')

        f.write('\n')
        f.close()

    def plot_network(self, dir_plots: str) -> None:
        """
        Plots the network.
        """
        n = pypsa.Network(self.network_file)
        plt.clf()
        n.plot(boundaries=[6, 15, 47, 55], bus_colors='darkorange', line_colors='darkgreen', color_geomap=True)
        plt.savefig(f"{dir_plots}/pypsa_eur_small.png", bbox_inches='tight', dpi=300)

    def get_geo_coordinates(self) -> dict:
        """
        Computes the geographic coordinates of each node.
        """
        n = pypsa.Network(self.network_file)
        nodes = n.buses.index
        node_geo = {}
        for node in nodes:
            x = n.buses[n.buses.index == node]['x'][0]
            y = n.buses[n.buses.index == node]['y'][0]
            node_geo[node] = {'x': x, 'y': y}
        return node_geo
