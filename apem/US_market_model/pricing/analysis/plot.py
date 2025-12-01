import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl

from apem.US_market_model.data.parsing.scenario import Scenario


def plot_avg_prices(avg_prices: pd.DataFrame, scenario: Scenario, file_plot: str = "") -> None:
    avg_prices.plot(xlim=(min(scenario.periods), max(scenario.periods)),
                    xlabel='period', ylabel='€/MWh')
    plt.savefig(file_plot, dpi=300)
    plt.close()


def plot_price_heatmap(file_heatmap: str, scenario: Scenario, avg_prices: dict = None, zonal_config: str = "", power_flow_model: str = ""):
    """Creates a heatmap with the (average) nodal (or zonal) prices for the underlying network.

    Args:
        file_heatmap (str): path to store the resulting heatmap
        scenario (Scenario): the scenario object
        avg_prices (dict, optional): average nodal (or zonal) prices
        zonal_config (str, optional): whether Zonal_NTC was used
    """

    # Define power flow model and create results directory, if not exists
    results_directory = os.path.join("US_results", f"{scenario.name}_results", power_flow_model or "DCOPF")
    os.makedirs(results_directory, exist_ok=True)
    zone_results_directory = os.path.join(results_directory, zonal_config) if zonal_config else results_directory

    # Require prices to be provided to avoid circular imports
    if avg_prices is None or not avg_prices:
        print("plot_price_heatmap: no prices provided, skipping plot.")
        return

    # If prices include periods (e.g., node-period keys or node strings with period), average by node
    sample_key = next(iter(avg_prices.keys()))
    if isinstance(sample_key, tuple) and len(sample_key) > 1:
        tmp = {}
        for (node, _), val in avg_prices.items():
            tmp.setdefault(node, []).append(val)
        avg_prices = {n: sum(vs) / len(vs) for n, vs in tmp.items()}
    elif isinstance(sample_key, str) and " " in sample_key:
        tmp = {}
        for k, val in avg_prices.items():
            node = k.split()[0]
            tmp.setdefault(node, []).append(val)
        avg_prices = {n: sum(vs) / len(vs) for n, vs in tmp.items()}

    # Collect node positions and prices
    nodes = [node for node in scenario.network.nodes if node in avg_prices]
    if not nodes:
        print("plot_price_heatmap: no nodes with prices, skipping plot.")
        return
    lats = [scenario.nodes_agents[n]["latitude"] for n in nodes]
    lons = [scenario.nodes_agents[n]["longitude"] for n in nodes]
    vals = [avg_prices[n] for n in nodes]

    # Collect edges for simple line drawing
    edges = [(u, v) for u, v in scenario.network.edges if u in avg_prices and v in avg_prices]

    plt.clf()
    fig, ax = plt.subplots(figsize=(10, 8))

    # Plot edges
    for u, v in edges:
        ax.plot(
            [scenario.nodes_agents[u]["longitude"], scenario.nodes_agents[v]["longitude"]],
            [scenario.nodes_agents[u]["latitude"], scenario.nodes_agents[v]["latitude"]],
            color="lightgray",
            linewidth=0.7,
            zorder=1,
        )

    # Plot nodes with price-based coloring
    sc = ax.scatter(lons, lats, c=vals, cmap="jet", vmin=min(vals), vmax=max(vals), s=50, zorder=2, edgecolors="k", linewidths=0.2)
    cbar = plt.colorbar(sc, ax=ax, label="€/MWh")

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Nodal prices")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    # If a path is provided, save; otherwise return the figure for interactive use
    if file_heatmap:
        plt.savefig(file_heatmap, bbox_inches="tight", dpi=300)
        plt.close(fig)
        return None
    return fig
