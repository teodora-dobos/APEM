import geopandas as gpd
import matplotlib as mpl
import os
import pandas as pd
import pypsa
from matplotlib import pyplot as plt
from shapely.geometry import Point, LineString
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="cartopy")


def plot_avg_prices(avg_prices, scenario, file_plot="") -> None:
    avg_prices.plot(xlim=(min(scenario.periods), max(scenario.periods)),
                    xlabel='period', ylabel='€/MWh')
    plt.savefig(file_plot, dpi=300)


def plot_pypsa_heatmap(file_pypsa_network: str, file_heatmap:str, avg_prices:dict=None, zonal_config:str="", dataset:str="") -> None:   
    """Creates a heatmap with the (average) nodal (or zonal) prices for the PyPSA network.

    Args:
        file_pypsa_network (str): path to the PyPSA network to be visualized
        file_heatmap (str): path to store the resulting heatmap
        avg_prices (dict, optional): average nodal (or zonal) prices
        zonal_config (str, optional): whether Zonal_NTC was used
        dataset (str, optional): the PyPSA dataset being used
    """
    
    # Define power flow model and create results directory, if not exists
    power_flow_model = "Zonal_NTC" if zonal_config else "DCOPF"
    results_directory = os.path.join("results", f"{dataset}_results", power_flow_model)
    os.makedirs(results_directory, exist_ok=True)
    
    # Load average prices, if not provided
    if avg_prices is None:
        avg_prices = PriceAnalysis.avg_node_prices()
    
    # Load PyPSA network
    n = pypsa.Network(file_pypsa_network)
    
    # Handle zonal mapping, if applicable
    if zonal_config:
        # Load csv file with node-to-zone mapping
        df_zones = pd.read_csv(os.path.join(results_directory, "node_to_zone_results", f"{zonal_config}.csv"), dtype={"node": str, "zone": str})
        
        # Ensure bus indices are strings
        n.buses.index = n.buses.index.astype(str)
        
        # Map zones to buses and drop invalid ones
        n.buses["zone"] = n.buses.index.map(df_zones.set_index("node")["zone"])
        n.buses.dropna(subset=["zone"], inplace=True)
        
        # Merge and aggregate prices per node
        df_prices = pd.DataFrame(list(avg_prices.items()), columns=["zone", "price"]).merge(df_zones, on="zone", how="inner")
        avg_prices = df_prices.groupby("node")["price"].mean().to_dict()
    
    else:
        # Filter buses based on available price data
        n.buses = n.buses[n.buses.index.isin(avg_prices.keys())]
       
    # Filter power lines with non-zero capacity 
    n.lines = n.lines[n.lines["s_nom"] > 0]

    # Extract longitude (x) & latitude (y) for buses, and assign prices
    CRS="EPSG:4326"
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
    map_germany = gpd.read_file("src/data/raw_data/gadm41_DEU_shp/gadm41_DEU_4.shp")
    map_germany.plot(ax=ax, color="lightgray", alpha=0.5)
    
    # Plot power lines
    line_df.plot(ax=ax, color="gray", linewidth=0.8, alpha=0.6)
    
    # Plot bus nodes with longitude & latitude and price-based color scale
    geo_df.plot(
        ax=ax,
        markersize=100,
        marker="o",
        column="price",
        cmap=cmap,
        legend=False, # disable automatic legend
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

    # Save heatmap
    plt.savefig(file_heatmap, bbox_inches="tight", dpi=300)