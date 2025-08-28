import geopandas as gpd
import matplotlib as mpl
import os
import pandas as pd

from matplotlib import pyplot as plt
from shapely.geometry import Point, LineString

from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.utils.paths import RAW_DATA_DIR


def plot_avg_prices(avg_prices: pd.DataFrame, scenario: Scenario, file_plot: str = "") -> None:
    avg_prices.plot(xlim=(min(scenario.periods), max(scenario.periods)),
                    xlabel='period', ylabel='€/MWh')
    plt.savefig(file_plot, dpi=300)
    plt.close()


def plot_price_heatmap(file_heatmap: str, scenario: Scenario, avg_prices: dict = None, zonal_config: str = "") -> None:
    """Creates a heatmap with the (average) nodal (or zonal) prices for the underlying network.

    Args:
        file_heatmap (str): path to store the resulting heatmap
        scenario (Scenario): the scenario object
        avg_prices (dict, optional): average nodal (or zonal) prices
        zonal_config (str, optional): whether Zonal_NTC was used
    """

    # Define power flow model and create results directory, if not exists
    power_flow_model = "Zonal_NTC" if zonal_config else "DCOPF"
    results_directory = os.path.join("results", f"{scenario.name}_results", power_flow_model)
    os.makedirs(results_directory, exist_ok=True)

    # Load average prices, if not provided
    if avg_prices is None:
        avg_prices = PriceAnalysis.avg_node_prices()

    # Store zonal price information for plotting purposes
    avg_prices_copy = avg_prices.copy()
    
    # Get nodes and edges from the network
    nodes = list(scenario.network.nodes)
    edges = scenario.network.edges(data=True)

    # Handle zonal mapping, if applicable
    if zonal_config:
        # Load csv file with node-to-zone mapping
        df_zones = pd.read_csv(os.path.join(results_directory, zonal_config, "node_to_zone.csv"),
                               dtype={"node": str, "zone": str})

        # Filter nodes that are in the networkx graph
        df_zones = df_zones[df_zones["node"].isin(nodes)]

        # Merge and aggregate prices per node
        df_prices = pd.DataFrame(list(avg_prices.items()), columns=["zone", "price"]).merge(
            df_zones, on="zone", how="inner")
        avg_prices = df_prices.groupby("node")["price"].mean().to_dict()

    else:
        # Filter nodes based on available price data
        nodes = [node for node in scenario.network.nodes if node in avg_prices]

    CRS = "EPSG:4326"
    
    # Create GeoDataFrame for nodes with longitude & latitude
    geo_df = gpd.GeoDataFrame(
        {
            "node": nodes,
            "latitude": [scenario.nodes_agents[node]["latitude"] for node in nodes],
            "longitude": [scenario.nodes_agents[node]["longitude"] for node in nodes],
        },
        crs=CRS,
           geometry=[
            Point(scenario.nodes_agents[node]["longitude"], scenario.nodes_agents[node]["latitude"])
            for node in nodes
        ]
    )
    geo_df["price"] = geo_df["node"].map(avg_prices)

    if zonal_config:
        geo_df = geo_df.merge(df_zones, on="node", how="left")

    # Create GeoDataFrame for edges
    line_df = gpd.GeoDataFrame(
        {
            "from_node": [u for u, v, data in edges],      
            "to_node": [v for u, v, data in edges],
            "B": [data["B"] for u, v, data in edges],
            "F_max": [data["F_max"] for u, v, data in edges]  
        }, 
        crs=CRS,
        geometry=[
            LineString([
                Point(scenario.nodes_agents[u]["longitude"], scenario.nodes_agents[u]["latitude"]),
                Point(scenario.nodes_agents[v]["longitude"], scenario.nodes_agents[v]["latitude"])
            ]) 
            for u, v, data in edges
        ]
    )

    # Set up color scale for prices
    norm = mpl.colors.Normalize(vmin=0, vmax=100)
    cmap = mpl.colormaps["jet"]

    # Clear previous plot and create figure
    plt.clf()
    fig, ax = plt.subplots(figsize=(15, 15))

    # Load and plot GADM map of Germany
    map_germany = gpd.read_file(RAW_DATA_DIR / "gadm41_DEU_shp" / "gadm41_DEU_1.shp")
    map_germany.plot(ax=ax, color="lightgray", alpha=0.5)
    map_germany.boundary.plot(ax=ax, color="lightgray", linewidth=1.0)  # show state borders

    # Plot power lines
    line_df.plot(ax=ax, color="gray", linewidth=1.0, alpha=0.7)

    # Plot bus nodes with longitude & latitude and price-based color scale
    geo_df.plot(
        ax=ax,
        markersize=100,
        marker="o",
        column="price",
        cmap=cmap,
        legend=False,  # disable automatic legend
        vmin=0,
        vmax=100
    )

    # Add colorbar
    cbar = plt.colorbar(
        mappable=mpl.cm.ScalarMappable(norm=norm, cmap=cmap),
        ax=ax,
        ticks=[0, 20, 40, 60, 80, 100],
        label="€/MWh"
    )
    cbar.set_ticklabels(['≤0', '20', '40', '60', '80', '≥100'])
    cbar.ax.tick_params(labelsize=13)
    cbar.set_label("€/MWh", fontsize=13)

    # Add text with price information
    # Note: We compute min, avg, and max based on the nodal prices!
    min_price = min(avg_prices_copy.values())
    max_price = max(avg_prices_copy.values())
    avg_price = sum(avg_prices_copy.values()) / len(avg_prices_copy)

    ax.text(
        0.05, 0.95,
        f"Min: {min_price:.2f} €/MWh\nAvg: {avg_price:.2f} €/MWh\nMax: {max_price:.2f} €/MWh",
        transform=ax.transAxes,
        fontsize=13,
        verticalalignment="top",
        bbox=dict(facecolor="white", alpha=0.8, edgecolor="gray", boxstyle="round,pad=0.5"),
        color="black"
    )

    if zonal_config:
        # dissolve nodes per zone to get a single geometry per zone
        zone_geo = geo_df.dissolve(by="zone")
    
        for zone, price in avg_prices_copy.items():
            # get the centroid of the combined geometry of the zone
            point = zone_geo.loc[zone].geometry.centroid
        
            ax.text(
                x=point.x,
                y=point.y,
                s=f"Zone {zone}: {price:.2f} €/MWh",
                fontsize=13,
                ha="center",
                color="black"
            )

    # Save heatmap
    plt.savefig(file_heatmap, bbox_inches="tight", dpi=300)
    plt.close(fig)
