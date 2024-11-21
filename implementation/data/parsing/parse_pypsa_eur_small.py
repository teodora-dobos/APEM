import pandas as pd
import networkx as nx
from collections import defaultdict
from implementation.data.parsing.parse_data import ParseData
from implementation.data.parsing.scenario import Scenario

path = './implementation/data/raw_data/pypsa_eur_small/'


class ParsePyPSAEurSmall(ParseData):

    def parse_data(self, day=None):
        df_sellers = pd.read_csv(path + 'sellers.csv')
        df_buyers = pd.read_csv(path + 'buyers.csv')
        network = nx.read_edgelist(path + 'network.csv', delimiter=',')
        periods = [i for i in range(1, 25)]

        node_map = pd.read_csv(path + 'nodes_agents.csv')
        nodes_agents = defaultdict(lambda: {'sellers': list(), 'buyers': list()})
        for node in node_map["node"].unique():
            nodes_agents[node]['buyers'].append(node)
            for seller in node_map[node_map["node"] == node]["seller"]:
                nodes_agents[node]['sellers'].append(seller)

        r_star = 'DE0 0'
        blocks_buyers = range(0, 0)
        blocks_sellers = range(1, 1 + 1)

        return Scenario('PyPSA_Eur_Small', df_buyers, df_sellers, network, nodes_agents, periods, blocks_buyers,
                        blocks_sellers, r_star)
