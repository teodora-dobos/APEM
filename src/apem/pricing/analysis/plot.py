import geopandas as gpd
import matplotlib as mpl
import os
import pandas as pd
import pypsa
from matplotlib import pyplot as plt
from shapely.geometry import Point, LineString


def plot_avg_prices(avg_prices, scenario, file_plot="") -> None:
    avg_prices.plot(xlim=(min(scenario.periods), max(scenario.periods)),
                    xlabel='period', ylabel='€/MWh')
    plt.savefig(file_plot, dpi=300)
    plt.close()


def plot_pypsa_heatmap(file_heatmap: str, dataset: str, avg_prices: dict = None, zonal_config: str = "") -> None:
    """Creates a heatmap with the (average) nodal (or zonal) prices for the PyPSA network.

    Args:
        file_heatmap (str): path to store the resulting heatmap
        dataset (str): the PyPSA dataset being used
        avg_prices (dict, optional): average nodal (or zonal) prices
        zonal_config (str, optional): whether Zonal_NTC was used
    """

    # Define power flow model and create results directory, if not exists
    power_flow_model = "Zonal_NTC" if zonal_config else "DCOPF"
    results_directory = os.path.join("results", f"{dataset}_results", power_flow_model)
    os.makedirs(results_directory, exist_ok=True)

    # Load average prices, if not provided
    if avg_prices is None:
        avg_prices = PriceAnalysis.avg_node_prices()

    # Store zonal price information for plotting purposes
    avg_prices_copy = avg_prices.copy()

    # Load PyPSA network
    if dataset == 'PyPSA_Eur_Large':
        n = pypsa.Network("apem/data/raw_data/pypsa_eur_large/elec_s_334m_ec_lv1.5_.nc")
    elif dataset == 'PyPSA_Eur_Small':
        n = pypsa.Network("src/apem/data/raw_data/pypsa_eur_small/elec_s_40_ec_lv1.5_.nc")

    # Handle zonal mapping, if applicable
    if zonal_config:
        # Load csv file with node-to-zone mapping
        df_zones = pd.read_csv(os.path.join(results_directory, zonal_config, "node_to_zone.csv"),
                               dtype={"node": str, "zone": str})

        # Ensure bus indices are strings
        n.buses.index = n.buses.index.astype(str)

        # Map zones to buses and drop invalid ones
        n.buses["zone"] = n.buses.index.map(df_zones.set_index("node")["zone"])
        n.buses.dropna(subset=["zone"], inplace=True)

        # Merge and aggregate prices per node
        df_prices = pd.DataFrame(list(avg_prices.items()), columns=["zone", "price"]).merge(df_zones, on="zone",
                                                                                            how="inner")
        avg_prices = df_prices.groupby("node")["price"].mean().to_dict()

    else:
        # Filter buses based on available price data
        n.buses = n.buses[n.buses.index.isin(avg_prices.keys())]

    # Filter power lines with non-zero capacity 
    n.lines = n.lines[n.lines["s_nom"] > 0]

    # Extract longitude (x) & latitude (y) for buses, and assign prices
    CRS = "EPSG:4326"
    geo_df = gpd.GeoDataFrame(
        n.buses,
        crs=CRS,
        geometry=[Point(xy) for xy in zip(n.buses["x"], n.buses["y"])]
    )
    geo_df["price"] = geo_df.index.map(avg_prices)

    # Create GeoDataFrame for lines
    line_df = gpd.GeoDataFrame(
        n.lines,
        crs=CRS,
        geometry=[
            LineString([(n.buses.loc[line["bus0"], "x"], n.buses.loc[line["bus0"], "y"]),
                        (n.buses.loc[line["bus1"], "x"], n.buses.loc[line["bus1"], "y"])])
            for _, line in n.lines.iterrows()
        ]
    )

    # Set up color scale for prices
    norm = mpl.colors.Normalize(vmin=0, vmax=100)
    cmap = mpl.colormaps["jet"]

    # Clear previous plot and create figure
    plt.clf()
    fig, ax = plt.subplots(figsize=(15, 15))

    # Load and plot GADM map of Germany
    map_germany = gpd.read_file("src/apem/data/raw_data/gadm41_DEU_shp/gadm41_DEU_1.shp")
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
        for zone, price in avg_prices_copy.items():
            ax.text(
                x=geo_df.loc[geo_df["zone"] == zone, "geometry"].iloc[0].x,
                y=geo_df.loc[geo_df["zone"] == zone, "geometry"].iloc[0].y,
                s=f"Zone {zone}: {price:.2f} €/MWh",
                fontsize=13,
                ha="center",
                color="black"
            )

    # Save heatmap
    plt.savefig(file_heatmap, bbox_inches="tight", dpi=300)
    plt.close(fig)
