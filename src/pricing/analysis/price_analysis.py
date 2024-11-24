import pandas as pd

from src.data.analysis.plot import plot_supply_demand
from src.pricing.algorithms.elmp import ELMP
from src.pricing.algorithms.ip import IP
from src.pricing.algorithms.min_mwp import MinMWP
from src.pricing.analysis.plot import plot_avg_prices, pypsa_heatmap


class PriceAnalysis:

    def __init__(self, scenario, allocation, pricing):
        self.scenario = scenario
        self.allocation = allocation
        self.pricing = pricing

    def compute_glocs(self, file_glocs="", mode="w"):
        pricing = self.pricing
        if pricing.status == 1:
            if pricing.glocs is None:
                elmp = ELMP()
                elmp_results = elmp.compute_prices(self.allocation, self.scenario, fixed_prices=pricing)
                if elmp_results.status == 1:
                    pricing.glocs = elmp_results.glocs
                else:
                    return None

            if file_glocs != "":
                file = open(file_glocs, mode)
                file.write(f"GLOCs buyers: {pricing.glocs.glocs_buyers}\n")
                file.write(f"GLOCs sellers: {pricing.glocs.glocs_sellers}\n")
                file.write(f"GLOCs network: {pricing.glocs.glocs_network}\n")
                file.write(f"Total GLOCs: {pricing.glocs.total_glocs}\n")
                file.write("\n")
                file.close()

            return pricing.glocs

        return None

    def compute_llocs(self, file_llocs="", mode="w"):
        pricing = self.pricing
        if pricing.status == 1:
            if pricing.llocs is None:
                ip = IP()
                ip_results = ip.compute_prices(self.allocation, self.scenario, fixed_prices=pricing)
                if ip_results.status == 1:
                    pricing.llocs = ip_results.llocs
                else:
                    return None

            if file_llocs != "":
                file = open(file_llocs, mode)
                file.write(f"LLOCs buyers: {pricing.llocs.llocs_buyers}\n")
                file.write(f"LLOCs sellers: {pricing.llocs.llocs_sellers}\n")
                file.write(f"LLOCs network: {pricing.llocs.llocs_network}\n")
                file.write(f"Total LLOCs: {pricing.llocs.total_llocs}\n")
                file.write("\n")
                file.close()

            return pricing.llocs

        return None

    def compute_mwps(self, file_mwps="", mode="w"):
        pricing = self.pricing
        if pricing.status == 1:
            if pricing.mwps is None:
                min_mwp = MinMWP()
                min_mwp_results = min_mwp.compute_prices(self.allocation, self.scenario, fixed_prices=pricing)
                if min_mwp_results.status == 1:
                    pricing.mwps = min_mwp_results.mwps
                else:
                    return None

            if file_mwps != "":
                file = open(file_mwps, mode)
                file.write(f"MWPs buyers: {pricing.mwps.mwps_buyers}\n")
                file.write(f"MWPs sellers: {pricing.mwps.mwps_sellers}\n")
                file.write(f"MWPs network: {pricing.mwps.mwps_network}\n")
                file.write(f"Total MWPs: {pricing.mwps.total_mwps}\n")
                file.write("\n")
                file.close()

            return pricing.mwps

        return None

    def compute_objectives(self, file_objectives="", mode="w"):
        self.compute_glocs(file_glocs=file_objectives, mode=mode)
        self.compute_llocs(file_llocs=file_objectives, mode="a")
        self.compute_mwps(file_mwps=file_objectives, mode="a")

        return self.pricing

    def performance_statistics(self, file_stats="", mode="w"):
        pricing = self.pricing

        if file_stats != "":
            f = open(file_stats, mode)
            f.write(f"Runtime in seconds: {pricing.runtime}\n")
            f.write(f"Number of Variables: {pricing.num_vars}\n")
            f.write(f"Number of Constraints: {pricing.num_constrs}\n")
            f.write(f"\n")
            f.close()

        return pricing.runtime, pricing.num_vars, pricing.num_constrs

    def avg_price(self, file_avg="", mode="w"):
        prices = self.pricing.node_prices.values()
        avg = sum(prices) / len(prices) if len(prices) > 0 else 0

        if file_avg != "":
            file = open(file_avg, mode)
            file.write(f"Average price: {avg}\n\n")
            file.close()

        return avg

    def avg_prices_periods(self, file_plot="", file_avg="", mode="w"):
        avg_prices = pd.DataFrame(columns=['period', 'avg_price'])
        for (_, t), p in self.pricing.node_prices.items():
            avg_prices.loc[len(avg_prices)] = {'period': t, 'avg_price': p}

        avg_prices = avg_prices.groupby(['period']).mean()

        if file_plot != "":
            plot_avg_prices(avg_prices, self.scenario, file_plot)

        avg_prices_dict = dict()

        for period in avg_prices.index.values:
            avg_prices_dict[period] = avg_prices.at[period, 'avg_price']

        if file_avg != "":
            file = open(file_avg, mode)
            for period, price in avg_prices_dict.items():
                file.write(f"Average price in period {period}: {price}\n")
            file.write("\n")
            file.close()

        return avg_prices_dict

    def avg_node_prices(self, file_avg="", mode="w"):
        avg_prices = pd.DataFrame(columns=['node', 'avg_price'])
        for (v, _), p in self.pricing.node_prices.items():
            avg_prices.loc[len(avg_prices)] = {'node': str(v), 'avg_price': p}

        avg_prices = avg_prices.groupby(['node']).mean()

        avg_prices_dict = dict()

        for node in avg_prices.index.values:
            avg_prices_dict[node] = avg_prices.at[node, 'avg_price']

        if file_avg != "":
            file = open(file_avg, mode)
            for node, price in avg_prices_dict.items():
                file.write(f"Average price at node {node}: {price}\n")
            file.write("\n")
            file.close()

        return avg_prices_dict

    def compute_all_statistics(self, dir_stats, file_pypsa_network=""):
        plot_supply_demand(dir_stats, self.scenario)

        file_stats = f"{dir_stats}/{self.pricing.used_algorithm}_stats.txt"
        self.compute_objectives(file_objectives=file_stats)
        self.performance_statistics(file_stats=file_stats, mode="a")
        self.avg_price(file_avg=file_stats, mode="a")
        self.avg_prices_periods(file_plot=f"{dir_stats}/{self.pricing.used_algorithm}_prices_periods.png",
                                file_avg=file_stats, mode="a")
        avg_prices = self.avg_node_prices(file_avg=file_stats, mode="a")

        if file_pypsa_network != "":
            pypsa_heatmap(file_pypsa_network, f"{dir_stats}/{self.pricing.used_algorithm}_heatmap.png",
                          avg_prices)
