from shapely.geometry import Point, LineString

import geopandas as gpd
import networkx as nx
import os
import pandas as pd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from apem.unit_based_model.utils.paths import RAW_DATA_DIR


class Scenario:
    """
    Buyers, sellers and network data.
    """

    def __init__(self, name: str, df_buyers: pd.DataFrame, df_sellers: pd.DataFrame, network: nx.Graph,
                 nodes_agents: dict, periods: list, blocks_buyers: range, blocks_sellers: range,
                 r_star: str):
        self.name = name
        self.df_buyers = df_buyers
        self.df_sellers = df_sellers
        self.network = network
        self.nodes_agents = nodes_agents
        self.periods = periods
        self.blocks_buyers = blocks_buyers
        self.blocks_sellers = blocks_sellers
        self.r_star = r_star

    def __str__(self):
        return self.name

    def analyse_scenario(self, results_root: str = "") -> None:
        """
        Computes scenario statistics.
        """
        count_sellers = len(self.df_sellers['seller'].unique())
        count_buyers = len(self.df_buyers['buyer'].unique())
        count_nodes = len(self.network.nodes)
        nodes_without_agents = [
            node for node, data in self.nodes_agents.items()
            if not data['buyers'] and not data['sellers']
        ]
        count_nodes_without_agents = len(nodes_without_agents)
        count_lines = len(self.network.edges)
        
        demand = self.df_buyers['max_dem'].sum()
        supply = self.df_sellers['max_prod'].sum()

        if 'carrier' in self.df_sellers.columns:
            energy_carriers = self.df_sellers['carrier'].unique().tolist()
            res_carriers = ['onwind', 'solar', 'offwind-ac', 'offwind-dc']
            res_sellers = self.df_sellers[self.df_sellers['carrier'].isin(res_carriers)]
            res_proportion = round(len(res_sellers) / len(self.df_sellers), 2)
            res_supply_proportion = round(res_sellers['max_prod'].sum() / supply, 2)

        # Define and create results directory, if not exists
        results_directory = results_root or f"./results/unit_based_model/{self.name}_results"
        os.makedirs(results_directory, exist_ok=True)

        # Write contents to scenario.txt file
        output_file = os.path.join(results_directory, f"{self.name}_base_scenario.txt")
        f = open(output_file, 'w+')
        f.write(f'Sellers: {count_sellers}\n')
        f.write(f'Buyers: {count_buyers}\n')
        f.write(f'Nodes: {count_nodes}\n')
        f.write(f'Nodes without agents: {count_nodes_without_agents}\n')
        f.write(f'Transmission lines: {count_lines}\n')
        f.write(f'Periods: {len(self.periods)}\n')
        if 'carrier' in self.df_sellers.columns:
            f.write(f'Energy carriers: {energy_carriers}\n')
            f.write(f'RES generator proportion in energy mix: {res_proportion}\n')
            f.write(f'RES supply proportion in energy mix: {res_supply_proportion}\n')
        
        f.write('\n')
        f.write(f'Demand: {demand}\n\n')
        for t in self.periods:
            demand_t = self.df_buyers[self.df_buyers['period'] == t]['max_dem'].sum()
            f.write(f'Demand period {t}: {demand_t}\n')          

        f.write('\n')
        f.write(f'Available supply: {supply}\n\n')
        for t in self.periods:
            supply_t = self.df_sellers[self.df_sellers['period'] == t]['max_prod'].sum()
            f.write(f'Available supply period {t}: {supply_t}\n')

        f.close()

    def plot_network(self, power_flow_model, zonal_config: str = "", results_root: str = "") -> None:
        """
        Plots the electricity network for the underlying scenario.
        
        Args:
            zonal_config (str, optional): if provided, nodes are colored according to their zonal assignments. Otherwise, they are colored black.
        """

        # Define power flow model and create results directory, if not exists
        base_dir = results_root or os.path.join("results", "unit_based_model", f"{self.name}_results")
        results_directory = os.path.join(base_dir, str(power_flow_model))
        os.makedirs(results_directory, exist_ok=True)
        zone_results_directory = os.path.join(results_directory, zonal_config) if zonal_config else results_directory

        # Get nodes and edges from the network
        nodes = list(self.network.nodes)
        edges = self.network.edges(data=True)
        
        CRS = "EPSG:4326"
        
        # Create GeoDataFrame for nodes with longitude & latitude
        geo_df = gpd.GeoDataFrame(
            {
                "node": nodes,
                "latitude": [self.nodes_agents[node]["latitude"] for node in nodes],
                "longitude": [self.nodes_agents[node]["longitude"] for node in nodes],
            },
            crs=CRS,
            geometry=[
                Point(self.nodes_agents[node]["longitude"], self.nodes_agents[node]["latitude"])
                for node in nodes
            ]
        )
        geo_df.index = geo_df["node"].astype(str)

        # Assign colors based on zonal configuration
        geo_df["color"] = "black"  # default color
        
        if zonal_config:
            # Load csv file with node-to-zone mapping, tolerate suffix variants
            os.makedirs(zone_results_directory, exist_ok=True)
            node_to_zone_path = os.path.join(zone_results_directory, "node_to_zone.csv")
            if not os.path.exists(node_to_zone_path):
                base_config = zonal_config.rsplit("_", 1)[0] if "_" in zonal_config else zonal_config
                alt_dir = os.path.join(results_directory, base_config)
                alt_path = os.path.join(alt_dir, "node_to_zone.csv")
                if os.path.exists(alt_path):
                    node_to_zone_path = alt_path
            if not os.path.exists(node_to_zone_path):
                print(f"plot_network: node_to_zone.csv not found for {zonal_config}, skipping plot.")
                return
            df_zones = pd.read_csv(node_to_zone_path, dtype={"node": str, "zone": str})

            # Merge geo_df with df_zones on the 'node'
            geo_df = geo_df.merge(df_zones[["node", "zone"]], left_index=True, right_on="node", how="inner")

            # Create colormap for zones
            unique_zones = sorted(geo_df["zone"].dropna().unique())
            ACER_BZR_colors = ['dodgerblue', 'coral', 'gold', 'darkviolet', 'green']

            # Determine color mapping based on the number of zones
            if len(unique_zones) <= 5:
                zone_to_color_mapping = {zone: color for zone, color in zip(unique_zones, ACER_BZR_colors)}
            else:
                cmap = plt.get_cmap("plasma", len(unique_zones) - 5)
                additional_colors = [cmap(i) for i in range(len(unique_zones) - 5)]
                zone_to_color_mapping = {zone: color for zone, color in zip(unique_zones[:5], ACER_BZR_colors)}
                zone_to_color_mapping.update({zone: color for zone, color in zip(unique_zones[5:], additional_colors)})

            # Assign colors to buses based on zones
            geo_df["color"] = geo_df["zone"].map(zone_to_color_mapping)

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
                    Point(self.nodes_agents[u]["longitude"], self.nodes_agents[u]["latitude"]),
                    Point(self.nodes_agents[v]["longitude"], self.nodes_agents[v]["latitude"])
                ]) 
                for u, v, data in edges
            ]
        )

        # Clear previous plot and create figure
        plt.clf()
        fig, ax = plt.subplots(figsize=(15, 15))

        # Load and plot GADM map of Germany
        map_germany = gpd.read_file(RAW_DATA_DIR / "gadm41_DEU_shp" / "gadm41_DEU_1.shp")
        map_germany.plot(ax=ax, color="lightgray", alpha=0.5)
        map_germany.boundary.plot(ax=ax, color="lightgray", linewidth=1.0)  # show state borders

        # Plot power lines
        line_df.plot(ax=ax, color="gray", linewidth=1.0, alpha=0.7)

        # Plot bus nodes with longitude & latitude 
        geo_df.plot(ax=ax, markersize=100, marker="o", color=geo_df["color"])

        if zonal_config:
            # Add legend with zone colors to the plot
            sorted_zones = sorted(unique_zones, key=str)
            legend_handles = [mpatches.Patch(color=zone_to_color_mapping[zone], label=f"Zone {zone}") for zone in
                              sorted_zones]
            ax.legend(handles=legend_handles, loc="upper left", title=f"Zones in {zonal_config}")

        # Save figure
        file_name = f"{self.name}_{zonal_config}" if zonal_config else self.name
        plt.savefig(f"{results_directory}/{file_name}_network.png", bbox_inches='tight', dpi=300)
        plt.close(fig)

