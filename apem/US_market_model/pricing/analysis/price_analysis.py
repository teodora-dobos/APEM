from typing import Optional, Tuple

import os
import pandas as pd

from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_NTC import Zonal_NTC
from apem.US_market_model.allocation.algorithms.zonal_clearing.zonal_fbmc_included import ZonalFBMC
from apem.US_market_model.allocation.allocation import Allocation
from apem.US_market_model.allocation.configuration import Configuration
from apem.US_market_model.data.analysis.plot import plot_supply_demand
from apem.US_market_model.data.parsing.scenario import Scenario
from apem.US_market_model.pricing.algorithms.elmp import ELMP
from apem.US_market_model.pricing.algorithms.ip import IP
from apem.US_market_model.pricing.algorithms.min_mwp import MinMWP
from apem.US_market_model.pricing.analysis.plot import plot_avg_prices, plot_price_heatmap
from apem.US_market_model.pricing.analysis.pricing import GLOCS, LLOCS, MWPS, Pricing


class PriceAnalysis:
    def __init__(
        self,
        scenario: Scenario,
        allocation: Allocation,
        pricing: Pricing,
        configuration: Configuration,
        base_scenario: Optional[Scenario] = None,
    ):
        self.scenario = scenario
        self.allocation = allocation
        self.pricing = pricing
        self.configuration = configuration
        self.base_scenario = base_scenario  # used only for zonal_NTC

    def compute_glocs(self, file_glocs: str = "", mode="w") -> Optional[GLOCS]:
        pricing = self.pricing
        if pricing.status == 1:
            if not pricing.glocs:
                elmp = ELMP()
                elmp_results = elmp.compute_prices(self.allocation, self.scenario, self.configuration, fixed_prices=pricing)
                if elmp_results.status == 1:
                    pricing.glocs = elmp_results.glocs
                else:
                    return None

            if file_glocs:
                file = open(file_glocs, mode)
                file.write(f"GLOCs buyers: {pricing.glocs.glocs_buyers}\n")
                file.write(f"GLOCs sellers: {pricing.glocs.glocs_sellers}\n")
                file.write(f"GLOCs network: {pricing.glocs.glocs_network}\n")
                file.write(f"Total GLOCs: {pricing.glocs.total_glocs}\n")
                file.write("\n")
                file.close()

            return pricing.glocs

        return None

    def compute_llocs(self, file_llocs: str = "", mode="w") -> Optional[LLOCS]:
        pricing = self.pricing
        if pricing.status == 1:
            if not pricing.llocs:
                ip = IP()
                ip_results = ip.compute_prices(self.allocation, self.scenario, self.configuration, fixed_prices=pricing)
                if ip_results.status == 1:
                    pricing.llocs = ip_results.llocs
                else:
                    return None

            if file_llocs:
                file = open(file_llocs, mode)
                file.write(f"LLOCs buyers: {pricing.llocs.llocs_buyers}\n")
                file.write(f"LLOCs sellers: {pricing.llocs.llocs_sellers}\n")
                file.write(f"LLOCs network: {pricing.llocs.llocs_network}\n")
                file.write(f"Total LLOCs: {pricing.llocs.total_llocs}\n")
                file.write("\n")
                file.close()

            return pricing.llocs

        return None

    def compute_mwps(self, file_mwps: str = "", mode="w") -> Optional[MWPS]:
        pricing = self.pricing
        if pricing.status == 1:
            if not pricing.mwps:
                min_mwp = MinMWP()
                min_mwp_results = min_mwp.compute_prices(self.allocation, self.scenario, self.configuration, fixed_prices=pricing)
                if min_mwp_results.status == 1:
                    pricing.mwps = min_mwp_results.mwps
                else:
                    return None

            if file_mwps:
                file = open(file_mwps, mode)
                file.write(f"MWPs buyers: {pricing.mwps.mwps_buyers}\n")
                file.write(f"MWPs sellers: {pricing.mwps.mwps_sellers}\n")
                file.write(f"MWPs network: {pricing.mwps.mwps_network}\n")
                file.write(f"Total MWPs: {pricing.mwps.total_mwps}\n")
                file.write("\n")
                file.close()

            return pricing.mwps

        return None

    def compute_objectives(self, file_objectives: str = "", mode="w") -> Pricing:
        self.compute_glocs(file_glocs=file_objectives, mode=mode)
        self.compute_llocs(file_llocs=file_objectives, mode="a")
        self.compute_mwps(file_mwps=file_objectives, mode="a")

        return self.pricing

    def performance_statistics(self, file_stats: str = "", mode="w") -> Tuple[float, float, float]:
        pricing = self.pricing

        if file_stats:
            f = open(file_stats, mode)
            f.write(f"Runtime in seconds: {pricing.runtime}\n")
            f.write(f"Number of Variables: {pricing.num_vars}\n")
            f.write(f"Number of Constraints: {pricing.num_constrs}\n\n")
            f.close()

        return pricing.runtime, pricing.num_vars, pricing.num_constrs

    def avg_price(self, file_avg: str = "", mode="w") -> float:
        prices = self.pricing.node_prices.values()
        avg_price = round(sum(prices) / len(prices), 2)

        if file_avg:
            f = open(file_avg, mode)
            f.write(f"Average price: {avg_price}\n")
            f.close()

        return avg_price

    def plot_avg_prices(self, file_plot: str = "") -> None:
        prices = self.pricing.node_prices
        plot_avg_prices(prices, self.scenario, file_plot=file_plot)

    def plot_price_heatmap(self, file_heatmap: str = "") -> None:
        prices = self.pricing.node_prices
        plot_price_heatmap(
            file_heatmap=file_heatmap,
            scenario=self.scenario,
            avg_prices=prices,
            zonal_config="",
            power_flow_model="DCOPF",
        )

    def plot_supply_demand(self, file_plot: str = "") -> None:
        plot_supply_demand(self.scenario, file_plot=file_plot)

    def analyse_results(self, folder_results: str, power_flow_model=None):
        file_objectives = os.path.join(folder_results, f"{power_flow_model}_objectives.txt")
        file_stats = os.path.join(folder_results, f"{power_flow_model}_stats.txt")
        file_avg = os.path.join(folder_results, f"{power_flow_model}_avg.txt")
        file_glocs = os.path.join(folder_results, f"{power_flow_model}_GLOCs.txt")
        file_llocs = os.path.join(folder_results, f"{power_flow_model}_LLOCs.txt")
        file_mwps = os.path.join(folder_results, f"{power_flow_model}_MWPs.txt")
        file_supply_demand = os.path.join(folder_results, f"{power_flow_model}_supply_demand.pdf")

        os.makedirs(folder_results, exist_ok=True)

        print(f"Compute stats and plotting data...")
        self.compute_objectives(file_objectives=file_objectives)
        self.performance_statistics(file_stats=file_stats)
        self.avg_price(file_avg=file_avg)
        self.plot_avg_prices(file_plot=os.path.join(folder_results, f"{power_flow_model}_avg_prices.pdf"))
        self.plot_price_heatmap(file_heatmap=os.path.join(folder_results, f"{power_flow_model}_heatmap.pdf"))
        self.plot_supply_demand(file_plot=file_supply_demand)

        return self.pricing
