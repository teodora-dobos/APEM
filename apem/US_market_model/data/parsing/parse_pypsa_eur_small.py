from collections import defaultdict

import networkx as nx
import pandas as pd

from apem.US_market_model.data.parsing.parse_data import ParseData
from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.utils.paths import RAW_DATA_DIR

path = RAW_DATA_DIR / "pypsa_eur_small"


class ParsePyPSAEurSmall(ParseData):
    def parse_data(self) -> Scenario:
        df_sellers = pd.read_csv(path / 'sellers.csv', dtype={'node': str})
        df_buyers = pd.read_csv(path / 'buyers.csv', dtype={
            'node': str,
            'buyer': str
        })
        df_coords = pd.read_csv(path / 'nodes_coords.csv', dtype={'node': str}).set_index('node')
        
        network = nx.read_edgelist(path / 'network.csv', nodetype=str, delimiter=',')
        periods = [i for i in range(1, 25)]

        nodes_agents = defaultdict(lambda: {'sellers': list(), 'buyers': list()})
        
        # add buyers to nodes_agents
        for node in df_buyers["node"].unique():
            nodes_agents[node]['buyers'].append(node)

        # add sellers to nodes_agents
        grouped_sellers = df_sellers.groupby("node")["seller"].unique()
        for node, sellers in grouped_sellers.items():
            nodes_agents[node]["sellers"].extend(sorted(sellers))

        # add coordinates to nodes_agents
        for node, coords in df_coords.iterrows():
            nodes_agents[node]["latitude"] = coords["latitude"]
            nodes_agents[node]["longitude"] = coords["longitude"]     

        r_star = 'DE0 0'
        blocks_buyers = range(0, 0)
        blocks_sellers = range(1, 1 + 1)

        return Scenario('PyPSA_Eur_Small', df_buyers, df_sellers, network, nodes_agents, periods, blocks_buyers,
                        blocks_sellers, r_star)