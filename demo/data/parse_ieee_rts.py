import pandas as pd
import csv
import networkx as nx
from collections import defaultdict

path = '../data/ieee_rts/'


def def_value_list():
    return {'sellers': list(), 'buyers': list()}


# contains, for each node (key), a dict {'sellers': [], 'buyers': []}
# with the sellers and buyers that are associated to this node
nodes_agents = defaultdict(def_value_list)


def read_generating_unit_locations(file):
    # get the node in which each seller is located
    sellers_to_node = dict()

    with open(file, newline='') as csvfile:
        content = csv.reader(csvfile, delimiter=' ', quotechar='|')
        for line in content:
            node = int(line[0])
            for i in range(1, len(line)):
                sellers_to_node[int(line[i].partition("(")[0])] = node + 100
    return sellers_to_node


def read_ieee_sellers():
    sellers_to_node = read_generating_unit_locations(path + 'gen_unit_loc.csv')

    df_sellers = pd.read_csv(path + 'grigg_gen_data_modified.csv', delim_whitespace=True,
                             names=['seller', 'size1', 'cost1', 'size2', 'cost2', 'size3', 'cost3', 'size4', 'cost4'],
                             header=None)

    # if a seller has less than 4 blocks of bids, replace the corresponding nan values with 0
    df_sellers = df_sellers.fillna(0)

    min_uptime = [1, 1, 8, 8, 1, 1, 8, 8, 1, 1, 1, 8, 8, 8, 12, 12, 12, 12, 12, 8, 8, 1, 1, 1, 1, 1, 1, 1, 1, 8, 8, 24]
    df_sellers['min_uptime'] = min_uptime
    df_sellers['no_load_cost'] = round(df_sellers['size1'] * df_sellers['cost1'], 2)
    df_sellers['min_prod'] = df_sellers['size1']
    df_sellers['max_prod'] = sum(df_sellers['size' + str(i)] for i in range(1, 5))
    df_sellers['period'] = 1

    df_sellers['node'] = df_sellers.apply(lambda x: sellers_to_node[x['seller']], axis=1)
    for s in sellers_to_node.keys():
        nodes_agents[sellers_to_node[s]]['sellers'].append(s)

    # extend the df with values for 24 periods
    # all column values (except for the period) are identical for all periods, for the same seller
    df_sellers_base_date = df_sellers.copy(deep=True)
    for p in range(2, 25):
        df_sellers_base_date['period'] = p
        df_sellers = pd.concat([df_sellers, df_sellers_base_date])

    return df_sellers


def read_hourly_loads(file):
    hourly_loads_percentages = dict()
    with open(file, newline='') as csvfile:
        content = csv.reader(csvfile, delimiter=' ', quotechar='|')
        period = 1
        for line in content:
            while '' in line:
                line.remove('')
            hourly_loads_percentages[period] = float(line[1]) / 100
            period += 1

    return hourly_loads_percentages


def read_ieee_buyers():
    hourly_loads_percentages = read_hourly_loads(path + 'hourly_loads.csv')

    base_loads = pd.read_csv(path + 'baseloads.csv', delim_whitespace=True,
                             names=['1', '2', '3', '%_sys_load', 'load_mw', 'load_mvar', 'peak_mw', 'peak_mvar'],
                             header=None)
    base_loads['buyer'] = [i for i in range(1, len(base_loads) + 1)]

    df_buyers = pd.read_csv(path + 'dem_bids.csv', delim_whitespace=True, header=None)
    df_buyers.columns = ['node', 'min_power_output', 'size1', 'val1', 'size2', 'val2', 'size3', 'val3']
    df_buyers['buyer'] = [i for i in range(1, len(df_buyers) + 1)]
    df_buyers['node'] = df_buyers['node'] + 100

    buyers = df_buyers['buyer'].unique().tolist()
    for b in buyers:
        nodes_agents[df_buyers.loc[df_buyers['buyer'] == b]['node'].iloc[0]]['buyers'].append(b)

    df_buyers['sum_sizes'] = sum(df_buyers['size' + str(i)] for i in range(1, 4))

    df_buyers['period'] = 0
    df_buyers['max_dem'] = 0

    df_buyers_base = df_buyers.copy(deep=True)  # used to construct the bids in each period

    for p in range(1, 25):
        # the df for the current period - will be appended to the big (multi-period) df
        df_buyers_current_period = df_buyers_base.copy(deep=True)

        df_buyers_current_period['period'] = p
        df_buyers_current_period['inelastic_dem'] = base_loads['peak_mw'] * hourly_loads_percentages[p] * \
                                                    (df_buyers_base['min_power_output'] / df_buyers_base['sum_sizes'])

        # define the block sizes depending on the period
        for i in range(1, 4):
            df_buyers_current_period['size' + str(i)] = base_loads['peak_mw'] * hourly_loads_percentages[p] * \
                                                        (df_buyers_base['size' + str(i)] / df_buyers_base['sum_sizes'])

        df_buyers_current_period['max_dem'] = sum(df_buyers_current_period['size' + str(i)] for i in range(1, 4)) + \
                                              df_buyers_current_period['inelastic_dem']

        df_buyers = pd.concat([df_buyers, df_buyers_current_period])

    df_buyers = df_buyers[df_buyers['period'] > 0]
    df_buyers = df_buyers.drop(['min_power_output', 'sum_sizes'], axis=1)

    return df_buyers


def read_ieee_branches():
    columns = ['ID', 'From', 'To', 'L', 'Perm', 'Dur', 'Tran.', 'R', 'X', 'B', 'Con', 'LTE', 'STE', 'Tr']
    df_branches = pd.read_csv(path + 'branches_modified.csv', delim_whitespace=True, names=columns, header=None)

    mean_B = df_branches[df_branches['B'] > 0]['B'].mean()
    df_branches.loc[df_branches['B'] == 0, 'B'] = mean_B

    df_branches.rename(columns={'Con': 'F_max'}, inplace=True)

    df_branches = df_branches[['From', 'To', 'B', 'F_max']]
    network = nx.from_pandas_edgelist(df_branches, 'From', 'To', ['B', 'F_max'])

    return network


def parse_ieee_rts_data():
    df_sellers = read_ieee_sellers()
    df_buyers = read_ieee_buyers()
    network = read_ieee_branches()

    periods = [i for i in range(1, 25)]

    R_star = 101
    blocks_buyers = 3
    blocks_sellers = 4

    return df_sellers, df_buyers, network, periods, nodes_agents, R_star, blocks_buyers, blocks_sellers
