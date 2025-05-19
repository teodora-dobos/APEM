import argparse
import os
import pypsa
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import warnings

# Suppress facecolor warnings
warnings.filterwarnings('ignore', message="facecolor will have no effect")

# Set the plotting style
plt.style.use("bmh")


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments
    """
    parser = argparse.ArgumentParser(description="Parse the PyPSA network data")
    parser.add_argument("network_name", type=str, choices=["pypsa_eur_small", "pypsa_eur_large"],
                        help="Name of the PyPSA network (valid options: pypsa_eur_small, pypsa_eur_large)")
    parser.add_argument("--compute_stats", action="store_true", help="Compute statistics (default: False)")
    return parser.parse_args()


def main():
    # Parse command-line arguments
    args = parse_args()
    NETWORK_NAME = args.network_name
    COMPUTE_STATS = args.compute_stats

    # Set network file based on its name
    print(f"Create CSV files for {NETWORK_NAME}")
    if NETWORK_NAME == "pypsa_eur_large":
        NETWORK_FILE = "elec_s_334m_ec_lv1.5_.nc"
    elif NETWORK_NAME == "pypsa_eur_small":
        NETWORK_FILE = "elec_s_40_ec_lv1.5_.nc"
    else:
        raise ValueError(f"Network name '{NETWORK_NAME}' is not valid.")

    # Define network and file path
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
    BASE_PATH = os.path.join(SCRIPT_DIR, NETWORK_NAME)
    PLOT_PATH = os.path.join(BASE_PATH, "plots")

    # Create directory (if not exists)
    os.makedirs(PLOT_PATH, exist_ok=True)

    # Load the network
    n = pypsa.Network(os.path.join(BASE_PATH, NETWORK_FILE))
    num_periods = len(n.snapshots)

    # Filter and rename generator columns
    n.generators = n.generators[
        ["carrier", "bus", "p_nom", "p_min_pu", "p_max_pu", "marginal_cost", "stand_by_cost", "min_up_time"]]
    n.generators = n.generators.rename(columns={"bus": "node"})
    n.generators = n.generators[n.generators["p_nom"] > 0]  # keep only generators with positive capacity
    n.generators.insert(0, "seller", range(1, len(n.generators) + 1))  # add a seller column

    # Export generator carrier statistics
    if COMPUTE_STATS:
        os.makedirs(os.path.join(BASE_PATH, "stats"), exist_ok=True)
        STAT_PATH = os.path.join(BASE_PATH, "stats")
        n.generators['carrier'].value_counts().to_csv(os.path.join(STAT_PATH, f"{NETWORK_NAME}_num_generators.csv"))

    else:
        print("INFO: Skipping statistics computation. To compute them, please provide the '--compute_stats' flag.")

    # Export nodes-agent relationships to a CSV file
    n.generators[["seller", "node"]].to_csv(os.path.join(BASE_PATH, "nodes_agents.csv"), index=False)

    # Rename, generate, and drop generator columns
    n.generators = n.generators.rename(columns={
        "marginal_cost": "cost1",
        "stand_by_cost": "no_load_cost",
        "min_up_time": "min_uptime"
    })
    n.generators.insert(3, "min_prod", n.generators["p_min_pu"] * n.generators["p_nom"])
    n.generators.drop(columns=["p_min_pu", "p_max_pu"], axis=1, inplace=True)

    # Initialize a DataFrame for generator production limits
    prod = pd.DataFrame(columns=["period", "generator", "p_max_pu"])
    count = 0
    for col in n.generators_t["p_max_pu"].columns:
        df = pd.DataFrame({"period": range(1, num_periods + 1),
                           "generator": col,
                           "p_max_pu": n.generators_t["p_max_pu"][col]})
        df.index = range(count, count + num_periods)
        count += num_periods

        if prod.empty:  # check if prod is empty before concatenating
            prod = df
        else:
            prod = pd.concat([prod, df], ignore_index=True)

    # Handle generators with missing time-series data
    for gen in n.generators.index:
        if gen not in n.generators_t["p_max_pu"].columns:
            df = pd.DataFrame({"period": range(1, num_periods + 1),
                               "generator": gen,
                               "p_max_pu": 1})
            df.index = range(count, count + num_periods)
            count += num_periods

            if prod.empty:  # check if prod is empty before concatenating
                prod = df
            else:
                prod = pd.concat([prod, df], ignore_index=True)

    # Merge production limits into the generators DataFrame
    n.generators = prod.join(n.generators, on="generator")

    # Remove entries with at least one NaN column
    n.generators = n.generators.dropna()

    # Aggregate and plot renewable production by carrier and period
    renewable_prod = n.generators[n.generators['generator'].isin(n.generators_t["p_max_pu"].columns)]
    renewable_prod = renewable_prod[['carrier', 'period', 'p_max_pu']]
    renewable_prod['period'] = renewable_prod['period'] - 1  # adjust period indexing
    renewable_prod = renewable_prod.groupby(['carrier', 'period']).mean()  # group by carrier and period
    plt.clf()
    pd.pivot_table(renewable_prod.reset_index(), index='period', columns='carrier', values='p_max_pu'
                   ).plot(xlim=(0, num_periods - 1), ylim=(0, 1.0), xlabel='hour', ylabel='p_max_pu')
    ax = plt.gca()
    ax.set_facecolor('xkcd:white')
    ax.grid(False)
    plt.legend().get_frame().set_facecolor('white')
    plt.savefig(os.path.join(PLOT_PATH, f"{NETWORK_NAME}_p_max_pu.png"), dpi=300)
    plt.close()

    # Calculate maximum production and size1 for generators and drop unused columns
    n.generators.insert(7, "max_prod", n.generators["p_max_pu"] * n.generators["p_nom"])
    n.generators.insert(8, "size1", n.generators["max_prod"])
    n.generators = n.generators.drop(columns=["p_max_pu", "p_nom"])
    n.generators["seller"] = n.generators["seller"].astype(int)
    n.generators["min_uptime"] = n.generators["min_uptime"].astype(int)

    # Export generator data to a CSV file
    n.generators.to_csv(os.path.join(BASE_PATH, "sellers.csv"), index=False)

    # Compute and export generator cost1 statistics
    if COMPUTE_STATS:
        generators_cost = n.generators[['carrier', 'cost1', 'max_prod']]
        generators_cost = generators_cost.groupby(['carrier']).mean()
        generators_cost = generators_cost.round(2)
        generators_cost.to_csv(os.path.join(STAT_PATH, f"{NETWORK_NAME}_carrier_cost.csv"))

    # Create a DataFrame for load demand
    dem = pd.DataFrame(columns=["period", "node", "buyer", "inelastic_dem", "max_dem"])
    count = 0
    for node in n.loads_t["p_set"].columns:
        df = pd.DataFrame({"period": range(1, num_periods + 1),
                           "node": node,
                           "buyer": node,
                           "inelastic_dem": n.loads_t["p_set"][node],
                           "max_dem": n.loads_t["p_set"][node]})
        df.index = range(count, count + num_periods)
        count += num_periods

        if dem.empty:  # check if prod is empty before concatenating
            dem = df
        else:
            dem = pd.concat([dem, df], ignore_index=True)

    # Export load data to a CSV file
    dem.to_csv(os.path.join(BASE_PATH, "buyers.csv"), index=False)

    # Process transmission line data
    n.lines = n.lines[["bus0", "bus1", "s_max_pu", "s_nom", "b"]]
    n.lines = n.lines[n.lines["s_nom"] > 0]  # keep only lines with positive capacity
    n.lines.insert(2, "F_max", n.lines["s_max_pu"] * n.lines["s_nom"])  # calculate maximum flow
    n.lines = n.lines.drop(columns=["s_max_pu", "s_nom"])
    n.lines = n.lines.rename(columns={"b": "B"})
    n.lines = n.lines.groupby(['bus0', 'bus1'], as_index=False).agg(
        {'F_max': 'sum', 'B': 'mean'})  # aggregate parallel lines

    # Create a network graph from the line data and export it to a CSV file
    network = nx.from_pandas_edgelist(n.lines, "bus0", "bus1", ["B", "F_max"])
    nx.write_edgelist(network, os.path.join(BASE_PATH, "network.csv"), delimiter=",")

    # Only keep buses that are part of the specified network nodes
    n.buses = n.buses[n.buses.index.isin(network.nodes)]

    # Iterate through network components and print their details
    for c in n.iterate_components(list(n.components.keys())[2:]):
        print("Component '{}' has {} entries".format(c.name, len(c.df)))

    # Plot the network with geographic boundaries
    plt.clf()
    n.plot(boundaries=[6, 15, 47, 55], bus_colors='darkorange', line_colors='darkgreen', color_geomap=True,
           bus_sizes=1e-2)
    plt.savefig(os.path.join(PLOT_PATH, f"{NETWORK_NAME}.png"), bbox_inches='tight', dpi=300)
    plt.close()


if __name__ == "__main__":
    main()
