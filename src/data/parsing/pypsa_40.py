import os
import pypsa
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt


paths = ['../plots']
for folder_path in paths:
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

plt.style.use("bmh")
n = pypsa.Network("../raw_data/pypsa_eur_small/elec_s_40_ec_lv1.5_.nc")

pd.set_option('display.max_rows', 20)
pd.set_option('display.max_columns', None)

n.generators = n.generators[
    ["carrier", "bus", "p_nom", "p_min_pu", "p_max_pu", "marginal_cost", "stand_by_cost", "min_up_time"]]

n.generators = n.generators.rename(columns={"bus": "node"})

n.generators = n.generators[n.generators["p_nom"] > 0]

n.generators.insert(0, "seller", range(1, len(n.generators) + 1))

nodes_agents = n.generators[["seller", "node"]]
nodes_agents.to_csv("../raw_data/pypsa_eur_small/nodes_agents.csv", index=False)

n.generators = n.generators.rename(columns={"marginal_cost": "cost1"})

n.generators = n.generators.rename(columns={"stand_by_cost": "no_load_cost"})

n.generators = n.generators.rename(columns={"min_up_time": "min_uptime"})

n.generators.insert(3, "min_prod", n.generators["p_min_pu"] * n.generators["p_nom"])

n.generators = n.generators.drop(["p_min_pu"], axis=1)

n.generators = n.generators.drop(["p_max_pu"], axis=1)

prod = pd.DataFrame(columns=["Generator", "period", "p_max_pu"])
count = 0
for col in n.generators_t["p_max_pu"].columns:
    df = pd.DataFrame({"period": range(1, 25),
                       "Generator": col,
                       "p_max_pu": n.generators_t["p_max_pu"][col]})
    df.index = range(count, count + 24)
    count += 24
    prod = pd.concat([prod, df])

for gen in n.generators.index:
    if gen not in n.generators_t["p_max_pu"].columns:
        df = pd.DataFrame({"period": range(1, 25),
                           "Generator": gen,
                           "p_max_pu": 1})
        df.index = range(count, count + 24)
        count += 24
        prod = pd.concat([prod, df])

n.generators = prod.join(n.generators, on="Generator")

renewable_prod = n.generators[n.generators['Generator'].isin(n.generators_t["p_max_pu"].columns)]
renewable_prod = renewable_prod[['carrier', 'period', 'p_max_pu']]
renewable_prod['period'] = renewable_prod['period'] - 1
renewable_prod = renewable_prod.groupby(['carrier', 'period']).mean()
plt.clf()
pd.pivot_table(renewable_prod.reset_index(),
               index='period', columns='carrier', values='p_max_pu'
               ).plot(xlim=(0, 23), ylim=(0, 1.0), xlabel='hour', ylabel='p_max_pu')
ax = plt.gca()
ax.set_facecolor('xkcd:white')
ax.grid(False)
plt.legend().get_frame().set_facecolor('white')
plt.savefig("../plots/pypsa_small_p_max_pu_small.png")

n.generators.insert(7, "max_prod", n.generators["p_max_pu"] * n.generators["p_nom"])

n.generators.insert(8, "size1", n.generators["max_prod"])

n.generators = n.generators.drop(columns=["p_max_pu", "p_nom"])

n.generators.to_csv("../raw_data/pypsa_eur_small/sellers.csv", index=False)

dem = pd.DataFrame(columns=["period", "node", "buyer", "inelastic_dem", "max_dem"])
count = 0
for node in n.loads_t["p_set"].columns:
    df = pd.DataFrame({"period": range(1, 25),
                       "node": node,
                       "buyer": node,
                       "inelastic_dem": n.loads_t["p_set"][node],
                       "max_dem": n.loads_t["p_set"][node]})
    df.index = range(count, count + 24)
    count += 24
    dem = pd.concat([dem, df])

dem.to_csv("../raw_data/pypsa_eur_small/buyers.csv", index=False)

n.lines = n.lines[["bus0", "bus1", "s_max_pu", "s_nom", "b"]]

n.lines = n.lines[n.lines["s_nom"] > 0]

n.lines.insert(2, "F_max", n.lines["s_max_pu"] * n.lines["s_nom"])
n.lines = n.lines.drop(columns=["s_max_pu", "s_nom"])
n.lines = n.lines.rename(columns={"b": "B"})

network = nx.from_pandas_edgelist(n.lines, "bus0", "bus1", ["B", "F_max"])
nx.write_edgelist(network, "../raw_data/pypsa_eur_small/network.csv", delimiter=",")

for c in n.iterate_components(list(n.components.keys())[2:]):
    print("Component '{}' has {} entries".format(c.name, len(c.df)))

plt.clf()
n.plot(boundaries=[6, 15, 47, 55], bus_colors='darkorange', line_colors='darkgreen', color_geomap=True)
plt.savefig("../plots/pypsa_eur_small.png", bbox_inches='tight', dpi=300)
