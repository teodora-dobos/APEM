import csv
from collections import defaultdict

import networkx as nx
import pandas as pd

from src.apem.data.parsing.common import def_value_list
from src.apem.data.parsing.parse_data import ParseData
from src.apem.data.parsing.scenario import Scenario

path = './src/apem/data/raw_data/pjm_2023_02_28/'


# keys are nodes, values are dicts {'sellers': [], 'buyers': []} representing the sellers and buyers located at nodes
nodes_agents = defaultdict(def_value_list)


def assign_buyers_id(x):
    if x == 'MID_ATLANTIC_REGION':
        return 1
    elif x == 'WESTERN_REGION':
        return 2
    elif x == 'PJM_RTO':
        return 3


def read_pjm_sellers():
    df_sellers = pd.read_csv(path + 'energy_market_offers_ordered.csv')
    size_list = ['mw' + str(i) for i in range(1, 21)]
    cost_list = ['bid' + str(i) for i in range(1, 21)]
    columns = ['bid_datetime_beginning_utc', 'unit_code', 'no_load_cost', 'min_runtime', 'max_ecomax',
               'min_ecomin'] + size_list + cost_list

    df_sellers = df_sellers[columns]

    df_sellers = df_sellers.rename(columns={'bid_datetime_beginning_utc': 'period', 'unit_code': 'seller',
                                            'max_ecomax': 'max_prod', 'min_ecomin': 'min_prod',
                                            'min_runtime': 'min_uptime'})
    df_sellers = df_sellers.rename(columns={'mw' + str(i): 'size' + str(i) for i in range(1, 21)})
    df_sellers = df_sellers.rename(columns={'bid' + str(i): 'cost' + str(i) for i in range(1, 21)})

    df_sellers['node'] = [1] * len(df_sellers)

    df_sellers.fillna(0, inplace=True)

    # ensure that there are bids for every period, for each seller (even if they are 0)
    periods = df_sellers['period'].unique().tolist()

    period = 1
    for p in periods:
        df_sellers = df_sellers.replace(p, period)
        period += 1

    periods = df_sellers['period'].unique().tolist()
    sellers = df_sellers['seller'].unique().tolist()

    # get the min uptime for each seller s, which is identical in all rows that correspond to s;
    # therefore, choose the first min_uptime - entry
    min_uptime = dict()
    for s in sellers:
        min_uptime[s] = df_sellers[df_sellers['seller'] == s]['min_uptime'].iloc[0]

    df_complem_sellers = pd.DataFrame(columns=df_sellers.columns)

    for p in periods:
        for s in sellers:
            # if for period p no row corresponding to seller s is found, append one row to df_sellers
            # that has all column values equal to 0 except for seller, period, min_uptime, node
            if not any(((df_sellers['seller'] == s) & (df_sellers['period'] == p)).to_list()):
                new_seller_entry = pd.DataFrame([[0] * df_complem_sellers.shape[1]], columns=df_complem_sellers.columns)
                new_seller_entry.loc[:, 'seller'] = s
                new_seller_entry.loc[:, 'period'] = p
                new_seller_entry.loc[:, 'min_uptime'] = min_uptime[s]
                new_seller_entry.loc[:, 'node'] = 1
                df_complem_sellers = pd.concat([df_complem_sellers, new_seller_entry])

    if not df_sellers.empty and not df_complem_sellers.empty:
        df_sellers = pd.concat([df_sellers, df_complem_sellers], axis=0)
    elif not df_complem_sellers.empty:
        df_sellers = df_complem_sellers.copy()

    sellers = df_sellers['seller'].unique().tolist()
    for s in sellers:
        nodes_agents[1]['sellers'].append(s)

    df_sellers['min_uptime'] = df_sellers['min_uptime'].astype(int)

    return df_sellers


def read_pjm_buyers():
    df_buyers = pd.read_csv(path + 'hrl_dmd_bids_ordered.csv')
    df_buyers = df_buyers[['datetime_beginning_utc', 'hrly_da_demand_bid', 'area']]

    df_buyers = df_buyers.rename(columns={'datetime_beginning_utc': 'period', 'hrly_da_demand_bid': 'size1'})

    df_buyers['buyer'] = df_buyers.apply(lambda row: assign_buyers_id(row.area), axis=1)
    df_buyers['inelastic_dem'] = df_buyers.apply(lambda row: row.size1 * 0.1, axis=1)

    # read randomly generated valuations
    file = open(path + 'valuations.csv', "r")
    valuations = list(csv.reader(file, delimiter=","))[0]
    valuations = [float(v) for v in valuations]
    file.close()
    df_buyers['val1'] = valuations[0:len(df_buyers)]

    df_buyers['node'] = [1] * len(df_buyers)
    df_buyers['max_dem'] = df_buyers['inelastic_dem'] + df_buyers['size1']

    df_buyers = df_buyers[['period', 'size1', 'buyer', 'inelastic_dem', 'val1', 'max_dem', 'node']]

    buyers = df_buyers['buyer'].unique().tolist()
    for b in buyers:
        nodes_agents[1]['buyers'].append(b)

    periods = df_buyers['period'].unique().tolist()
    period = 1
    for p in periods:
        df_buyers = df_buyers.replace(p, period)
        period += 1

    return df_buyers


def read_pjm_branches():
    network = nx.Graph()
    network.add_node(1)
    return network


class ParsePJM(ParseData):

    def parse_data(self, day=None) -> Scenario:
        """Parse the PJM data.

        :return: Scenario object
        """
        df_sellers = read_pjm_sellers()
        df_buyers = read_pjm_buyers()
        network = read_pjm_branches()

        periods = df_buyers['period'].unique().tolist()

        r_star = 1
        blocks_buyers = range(1, 1 + 1)
        blocks_sellers = range(1, 20 + 1)

        return Scenario('PJM', df_buyers, df_sellers, network, nodes_agents, periods, blocks_buyers,
                        blocks_sellers, r_star)
