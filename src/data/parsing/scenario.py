from shapely.geometry import Point, LineString
from typing import Union, Optional

import geopandas as gpd
import networkx as nx
import os
import pandas as pd
import pypsa
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

class Scenario:
    """
    Buyers, sellers and network data.
    """

    def __init__(self, name: str, df_buyers: pd.DataFrame, df_sellers: pd.DataFrame, network: nx.Graph,
                 nodes_agents: dict, periods: list, blocks_buyers: range, blocks_sellers: range,
                 r_star: Union[str, int], network_file: Optional[str] = None):
        self.name = name
        self.df_buyers = df_buyers
        self.df_sellers = df_sellers
        self.network = network
        self.nodes_agents = nodes_agents
        self.periods = periods
        self.blocks_buyers = blocks_buyers
        self.blocks_sellers = blocks_sellers
        self.r_star = r_star
        self.network_file = network_file


    def __str__(self):
        return self.name


    def analyse_scenario(self) -> None:
        """
        Computes scenario statistics.
        """
        count_sellers = len(self.df_sellers['seller'].unique())
        count_buyers = len(self.df_buyers['buyer'].unique())
        count_nodes = len(self.df_sellers['node'].unique())

        energy_carriers = self.df_sellers['carrier'].unique().tolist()

        res_carriers = ['onwind', 'solar', 'offwind-ac', 'offwind-dc']
        res_sellers = self.df_sellers[self.df_sellers['carrier'].isin(res_carriers)]
        res_proportion = round(len(res_sellers) / len(self.df_sellers), 2)
        demand = self.df_buyers['max_dem'].sum()
        supply = self.df_sellers['max_prod'].sum()
        
        # Define and create results directory, if not exists
        results_directory = f"./results/{self.name}_results"
        os.makedirs(results_directory, exist_ok=True)
            
        # Write contents to scenario.txt file
        output_file = os.path.join(results_directory, f"{self.name}_nodal_scenario.txt")
        f = open(output_file, 'w+')
        f.write(f'Sellers: {count_sellers}\n')
        f.write(f'Buyers: {count_buyers}\n')
        f.write(f'Nodes: {count_nodes}\n')
        f.write(f'Transmission lines: {len(self.network)}\n')
        f.write(f'Periods: {len(self.periods)}\n')
        f.write(f'Energy carriers: {energy_carriers}\n')
        f.write(f'RES proportion in energy mix: {res_proportion}\n')
        f.write(f'Demand: {demand}\n\n')

        for t in self.periods:
            demand_t = self.df_buyers[self.df_buyers['period'] == t]['max_dem'].sum()
            f.write(f'Demand period {t}: {demand_t}\n')

        f.write('\n')
        f.write(f'Available supply: {supply}\n\n')
        for t in self.periods:
            supply_t = self.df_sellers[self.df_sellers['period'] == t]['max_prod'].sum()
            f.write(f'Available supply period {t}: {supply_t}\n')

        f.write('\n')
        f.close()


    def plot_network(self, zonal_config:str="") -> None:
        """
        Plots the PyPSA network.
        
        Args:
            zonal_config (str, optional): if provided, nodes are colored according to their zonal assignments. Otherwise, they are colored black.
        """     
        
        # Define power flow model and create results directory, if not exists
        power_flow_model = "Zonal_NTC" if zonal_config else "DCOPF"
        results_directory = os.path.join("results", f"{self.name}_results", power_flow_model)
        os.makedirs(results_directory, exist_ok=True)
            
        # Load PyPSA network
        n = pypsa.Network(self.network_file)
        
        # Override network with the corresponding nodal PyPSA network, if required
        if zonal_config and self.name == 'PyPSA_Eur_Large':
            n = pypsa.Network("src/data/raw_data/pypsa_eur_large/elec_s_334m_ec_lv1.5_.nc")
        elif zonal_config and self.name == 'PyPSA_Eur_Small':
            n = pypsa.Network("src/data/raw_data/pypsa_eur_small/elec_s_40_ec_lv1.5_.nc")
        
        # Filter power lines with non-zero capacity 
        n.lines = n.lines[n.lines["s_nom"] > 0]
        
        # Extract longitude (x) & latitude (y) for buses
        CRS="EPSG:4326"
        geo_df = gpd.GeoDataFrame(
            n.buses, 
            crs=CRS, 
            geometry=[Point(xy) for xy in zip(n.buses["x"], n.buses["y"])]
        )      
    
        # Assign colors based on zonal configuration
        geo_df["color"] = "black" # default color
        if zonal_config:
            # Load csv file with node-to-zone mapping
            df_zones = pd.read_csv(os.path.join(results_directory, zonal_config, "node_to_zone.csv"), dtype={"node": str, "zone": str})  
            
            # Merge geo_df with df_zones on the 'node'
            geo_df = geo_df.merge(df_zones[["node", "zone"]], left_index=True, right_on="node", how="inner")
            
            # Create colormap for zones
            unique_zones = geo_df["zone"].dropna().unique()
            cmap = plt.get_cmap("plasma", len(unique_zones))
            zone_to_color_mapping = {zone: cmap(i) for i, zone in enumerate(unique_zones)}

            # Assign colors to buses based on zones
            geo_df["color"] = geo_df["zone"].map(zone_to_color_mapping)  
           
        # Create GeoDataFrame for lines
        line_df = gpd.GeoDataFrame(
            n.lines, 
            crs=CRS, 
            geometry=[
                LineString([(n.buses.loc[line["bus0"], "x"], n.buses.loc[line["bus0"], "y"] ),
                            (n.buses.loc[line["bus1"], "x"], n.buses.loc[line["bus1"], "y"] )])
                for _, line in n.lines.iterrows()
            ]
        )       
    
        # Clear previous plot and create figure
        plt.clf()
        fig, ax = plt.subplots(figsize=(15, 15))
        
        # Load and plot GADM map of Germany
        map_germany = gpd.read_file("src/data/raw_data/gadm41_DEU_shp/gadm41_DEU_4.shp")
        map_germany.plot(ax=ax, color="lightgray", alpha=0.5)
        
        # Plot power lines
        line_df.plot(ax=ax, color="gray", linewidth=0.8, alpha=0.6)

        # Plot bus nodes with longitude & latitude 
        geo_df.plot(
            ax=ax,
            markersize=50,
            marker="o",
            color=geo_df["color"]
        )
        
        if zonal_config:
            # Add legend with zone colors to the plot
            sorted_zones = sorted(unique_zones, key=str)
            legend_handles = [mpatches.Patch(color=zone_to_color_mapping[zone], label=f"Zone {zone}") for zone in sorted_zones]
            ax.legend(handles=legend_handles, loc="upper left", title=f"Zones in {zonal_config}")

        # Save figure
        file_name = f"{self.name}_{zonal_config}" if zonal_config else self.name
        plt.savefig(f"{results_directory}/{file_name}_network.png", bbox_inches='tight', dpi=300)
    
    
    def get_geo_coordinates(self) -> dict:
        """
        Computes the geographic coordinates of each node.
        """
        n = pypsa.Network(self.network_file)
        nodes = n.buses.index
        node_geo = {}
        for node in nodes:
            x = n.buses[n.buses.index == node]['x'][0]
            y = n.buses[n.buses.index == node]['y'][0]
            node_geo[node] = {'x': x, 'y': y}
        return node_geo
