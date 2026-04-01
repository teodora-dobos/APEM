import csv
import json
from collections import defaultdict

import networkx as nx
import numpy as np
import pandas as pd

from apem.unit_based_model.data.parsing.common import def_value_list, def_value_simple_list
from apem.unit_based_model.data.parsing.parse_data import ParseData
from apem.unit_based_model.data.parsing.scenario import Scenario
from apem.unit_based_model.utils.paths import RAW_DATA_DIR

path = RAW_DATA_DIR / "arpa_e-scenario-5"

MAX_SUSCEPTANCE = 2
MIN_SUSCEPTANCE = 0.01


def calculate_susceptance(resistance, reactance) -> float:
    """Calculates the susceptance, given the resistance and reactance: https://en.wikipedia.org/wiki/Susceptance.

    :param resistance: resistance R
    :param reactance: reactance X
    :return: susceptance B
    """
    impedance = resistance + reactance * 1j
    admittance = 1 / impedance
    susceptance = np.imag(admittance)
    if susceptance > MAX_SUSCEPTANCE:
        susceptance = MAX_SUSCEPTANCE
    if susceptance < MIN_SUSCEPTANCE:
        susceptance = MIN_SUSCEPTANCE
    return susceptance


# keys are nodes, values are dicts {'sellers': [], 'buyers': []} representing the sellers and buyers located at nodes
nodes_agents = defaultdict(def_value_list)


def read_arpa_sellers(path) -> pd.DataFrame:
    """Create a dataframe containing sellers data.

    :param path: path where the ARPA scenario can be found
    :return: sellers dataframe
    """
    with open(path / 'case.json', 'r') as f:
        data = json.load(f)

        sellers = data['generators']
        df_sellers = pd.DataFrame(sellers)

        df_sellers = df_sellers[['bus', 'oncost', 'cblocks']]

        # define no_load_cost as on_cost
        df_sellers = df_sellers.rename(columns={'oncost': 'no_load_cost', 'bus': 'node'})

        df_sellers = df_sellers.loc[df_sellers['cblocks'].str.len() >= 4]
        sellers_count = len(df_sellers)

        max_prod_list = []

        sizes_dict = defaultdict(def_value_simple_list)
        costs_dict = defaultdict(def_value_simple_list)

        index_sellers = []

        count = 0
        for index, row in df_sellers.iterrows():
            blocks = row['cblocks']
            max_prod = 0
            if len(blocks) >= 4:
                index_sellers.append(count)
                for l in range(4):
                    max_prod += float(blocks[l]['pmax'])
                    sizes_dict[l + 1].append(float(blocks[l]['pmax']))
                    costs_dict[l + 1].append(float(blocks[l]['c']))

                max_prod_list.append(max_prod)
            count += 1

        df_sellers['max_prod'] = max_prod_list

        for l in range(1, 5):
            df_sellers['size' + str(l)] = sizes_dict[l]
            df_sellers['cost' + str(l)] = costs_dict[l]

        df_sellers = df_sellers.drop('cblocks', axis=1)

        df_sellers['seller'] = [i for i in range(1, len(df_sellers) + 1)]
        df_sellers['period'] = [1] * sellers_count
        df_sellers['min_uptime'] = [0] * sellers_count

        # get the minimum production levels
        min_prod_list = []
        index = 0
        with open(path  / 'raw_sellers.csv', 'r') as f_raw_sellers:
            content = csv.reader(f_raw_sellers, delimiter=',', quotechar='|')
            for seller in content:
                if index in index_sellers:
                    min_output = float(seller[17])
                    min_prod_list.append(min_output)
                index += 1

        df_sellers['min_prod'] = min_prod_list

    for s in range(1, sellers_count + 1):
        nodes_agents[df_sellers.loc[(df_sellers['seller'] == s), 'node'].iloc[0]]['sellers'].append(s)

    return df_sellers


def read_arpa_buyers(path) -> pd.DataFrame:
    """Create a dataframe containing buyers data.

    :param path: path where the ARPA scenario can be found
    :return: buyers dataframe
    """
    # set the price-inelastic demand
    SBASE = 100  # from case.raw, first line
    p0_dict, pl_dict = {}, {}
    with open(path / 'raw_buyers.csv', 'r') as f_raw_buyers:
        content = csv.reader(f_raw_buyers, delimiter=',', quotechar='|')
        buyer_index = 1
        for buyer in content:
            PL = float(buyer[5])
            pl_dict[buyer_index] = PL
            p0 = PL / SBASE
            p0_dict[buyer_index] = p0
            buyer_index += 1

    # construct buyers dataframe
    with open(path / 'case.json', 'r') as f:
        data = json.load(f)
        buyers = data['loads']
        df_buyers = pd.DataFrame(buyers)
        df_buyers = df_buyers[df_buyers['cblocks'].str.len() >= 3]
        buyers_count = len(df_buyers)

        df_buyers['buyer'] = [i for i in range(1, buyers_count + 1)]
        df_buyers['period'] = [1] * buyers_count

        inelastic_dem_list = []
        for b in range(1, buyers_count + 1):
            inelastic_dem = df_buyers.loc[(df_buyers['buyer'] == b), 'tmin'].iloc[0] * p0_dict[b]

            inelastic_dem_list.append(inelastic_dem)

        df_buyers['inelastic_dem'] = inelastic_dem_list

        max_dem_list = []

        sizes_dict = defaultdict(def_value_simple_list)
        vals_dict = defaultdict(def_value_simple_list)

        max_val = None

        for index, row in df_buyers.iterrows():
            blocks = row['cblocks']
            max_dem = 0
            if len(blocks) >= 3:
                for l in range(3):
                    max_dem += float(blocks[l]['pmax'])
                    sizes_dict[l + 1].append(float(blocks[l]['pmax']))
                    vals_dict[l + 1].append(float(blocks[l]['c']))

                    if max_val is None:
                        max_val = float(blocks[l]['c'])
                    elif max_val < float(blocks[l]['c']):
                        max_val = float(blocks[l]['c'])

                max_dem_list.append(max_dem)

        df_buyers['max_dem'] = max_dem_list

        for l in range(1, 4):
            df_buyers['size' + str(l)] = sizes_dict[l]
            df_buyers['val' + str(l)] = vals_dict[l]

    df_buyers = df_buyers.rename(columns={'bus': 'node'})
    df_buyers = df_buyers.drop(['cblocks', 'id', 'tmin', 'tmax', 'prumax', 'prdmax', 'prumaxctg', 'prdmaxctg'], axis=1)

    for b in range(1, buyers_count + 1):
        nodes_agents[df_buyers.loc[(df_buyers['buyer'] == b), 'node'].iloc[0]]['buyers'].append(b)

    return df_buyers


def read_arpa_branches(path) -> nx.Graph:
    """Read branches information and create a transmission network.

    :param path: path where the ARPA scenario can be found
    :return: a graph with minimum/maximum capacity and susceptance specified for each branch
    """
    from_list, to_list, B_list, F_max_list = [], [], [], []

    # non-transformer branch raw_data
    with open(path / 'raw_branches.csv', newline='') as csvfile:
        content = csv.reader(csvfile, delimiter=',', quotechar='|')
        for branch in content:
            resistance = float(branch[3])
            reactance = float(branch[4])
            susceptance = calculate_susceptance(resistance, reactance)

            From = int(branch[0])
            To = int(branch[1])
            B = susceptance
            F_max = float(branch[6])

            from_list.append(int(From))
            to_list.append(int(To))
            B_list.append(B)
            F_max_list.append(F_max)

            from_list.append(int(To))
            to_list.append(int(From))
            B_list.append(B)
            F_max_list.append(F_max)

    # transformer branch raw_data
    # a transformer is defined in 4 lines
    with open(path / 'raw_transformers.csv', newline='') as csvfile:
        content = csv.reader(csvfile, delimiter=',', quotechar='|')
        for ind, row in enumerate(content, 1):
            if (ind - 1) % 4 == 0:
                from_bus = row[0]
                to_bus = row[1]
            if (ind - 1) % 4 == 1:
                resistance = float(row[0])
                reactance = float(row[1])
                susceptance = calculate_susceptance(resistance, reactance)
            if (ind - 1) % 4 == 2:
                capacity = float(row[3])
            if (ind - 1) % 4 == 3:
                from_list.append(int(from_bus))
                to_list.append(int(to_bus))
                B_list.append(susceptance)
                F_max_list.append(capacity)

                from_list.append(int(to_bus))
                to_list.append(int(from_bus))
                B_list.append(susceptance)
                F_max_list.append(capacity)

    df_branches = pd.DataFrame()
    df_branches['From'] = from_list
    df_branches['To'] = to_list
    df_branches['B'] = B_list
    df_branches['F_max'] = F_max_list

    network = nx.from_pandas_edgelist(df_branches, 'From', 'To', ['B', 'F_max'])

    return network


class ParseARPA(ParseData):

    def parse_data(self, day=None) -> Scenario:
        global nodes_agents
        nodes_agents = defaultdict(def_value_list)
        df_sellers = read_arpa_sellers(path)
        df_buyers = read_arpa_buyers(path)
        network = read_arpa_branches(path)

        periods = [1]

        r_star = df_sellers.head(1)['node'].iloc[0]
        blocks_buyers = range(1, 3 + 1)
        blocks_sellers = range(1, 4 + 1)

        return Scenario('ARPA', df_buyers, df_sellers, network, nodes_agents, periods, blocks_buyers,
                        blocks_sellers, r_star)

