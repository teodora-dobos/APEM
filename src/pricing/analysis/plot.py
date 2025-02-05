import geopandas as gpd
import matplotlib as mpl
import pypsa
from matplotlib import pyplot as plt
from shapely.geometry import Point, LineString
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="cartopy")


def plot_avg_prices(avg_prices, scenario, file_plot="") -> None:
    avg_prices.plot(xlim=(min(scenario.periods), max(scenario.periods)),
                    xlabel='period', ylabel='€/MWh')
    plt.savefig(file_plot, dpi=300)


def plot_pypsa_heatmap(file_pypsa_network: str, file_heatmap:str, avg_prices:dict=None) -> None:   
    """Creates a heatmap with the (average) nodal prices for the PyPSA network.

    Args:
        file_pypsa_network (str): path to the PyPSA network to be visualized
        file_heatmap (str): path to store the results
        avg_prices (dict, optional): average nodal prices
    """
    
    if avg_prices is None:
        avg_prices = PriceAnalysis.avg_node_prices()
    
    # Load PyPSA network
    n = pypsa.Network(file_pypsa_network)
    
    # Filter buses and lines based on available price data
    n.buses = n.buses[n.buses.index.isin(avg_prices.keys())]
    n.lines = n.lines[n.lines["s_nom"] > 0]

    # Extract longitude (x) & latitude (y)
    geometry = [Point(xy) for xy in zip(n.buses["x"], n.buses["y"])]
    crs = "EPSG:4326"  # define coordinate reference system
    geo_df = gpd.GeoDataFrame(n.buses, crs=crs, geometry=geometry)
    
    # Add average nodal prices as column to buses & extract line geometries
    geo_df["Price"] = geo_df.index.map(avg_prices)  # map prices to bus indices
    line_geometries = [
        LineString([(n.buses.loc[line["bus0"], "x"], n.buses.loc[line["bus0"], "y"]),
                    (n.buses.loc[line["bus1"], "x"], n.buses.loc[line["bus1"], "y"])])
        for _, line in n.lines.iterrows()
    ]
    line_df = gpd.GeoDataFrame(n.lines, crs=crs, geometry=line_geometries)
    
    # Normalize color scale
    norm = mpl.colors.Normalize(vmin=0, vmax=100)
    cmap = mpl.colormaps["jet"]
    
    # Clear previous plot
    plt.clf()
    
    # Create figure and axis
    fig, ax = plt.subplots(figsize=(15, 15))

    # Plot GADM map of Germany
    map_germany = gpd.read_file("src/data/raw_data/gadm41_DEU_shp/gadm41_DEU_4.shp")
    map_germany.plot(ax=ax, color="lightgray", alpha=0.5)
    
    # Plot power lines
    line_df.plot(ax=ax, color="gray", linewidth=0.8, alpha=0.6)
    
    # Plot bus nodes with longitude & latitude
    geo_df.plot(
        ax=ax,
        markersize=100,
        marker="o",
        column="Price",
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

    # Save figure
    plt.savefig(file_heatmap, bbox_inches="tight", dpi=300)